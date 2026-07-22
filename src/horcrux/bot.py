from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

import discord
from discord import app_commands

from .absorb import run_absorb
from .config import Config, VaultConfig, load_vault_config
from .diagnose import diagnose
from .feedback import run_feedback
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .records import save_record
from .seed import run_seed

MAX_ROUNDS = 3       # 재질문 최대 횟수
REPLY_TIMEOUT = 600  # 재질문 응답 대기 (초)
MSG_LIMIT = 2000     # 디스코드 메시지 길이 제한

# ponytail: 전역 볼트 쓰기 락 — 동시 저장 시 record id 순번 경쟁(덮어쓰기)·
# _absorb_log.json 경쟁 방지. absorb_after·/absorb·/seed는 LLM 생성 동안까지 이 락을
# 쥐고 있어 그 사이 다른 세션의 저장(finalize_log)이 전부 막힘 — 처리량 병목의 실제
# 천장은 LLM 호출 시간. 문제되면 레코드 저장 락과 absorb 직렬화 락을 분리.
_VAULT_LOCK = threading.Lock()


def _locked(fn, *args):
    """볼트 쓰기 진입점 공용 래퍼 — 슬래시 커맨드(run_absorb/run_seed/run_feedback)도
    반드시 이 경유로 호출해 락을 우회하지 않게 한다."""
    with _VAULT_LOCK:
        return fn(*args)


@dataclass
class LogSession:
    text: str          # 누적 원문 (원본 + 추가 답변)
    parsed: ParsedLog
    rounds: int = 0    # 지금까지 던진 재질문 횟수
    files: list[tuple[str, bytes]] = field(default_factory=list)  # 첨부 (파일명, 내용)


def split_message(text: str, limit: int = MSG_LIMIT) -> list[str]:
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def route(channel_name: str | None, log_channel: str, ask_channel: str) -> str | None:
    """채널 이름 → 처리 종류. 매핑 밖 채널·DM은 None (무시)."""
    if channel_name == log_channel:
        return "log"
    if channel_name == ask_channel:
        return "ask"
    return None


def save_attachments(vault: Path, rec_id: str, files: list[tuple[str, bytes]]) -> list[str]:
    """첨부를 볼트에 저장하고 옵시디언 임베드 링크 목록 반환. 내용 분석은 없음(보관만)."""
    if not files:
        return []
    d = Path(vault) / "raw" / "attachments" / rec_id
    d.mkdir(parents=True, exist_ok=True)
    links = []
    used: set[str] = set()
    for name, data in files:
        safe = os.path.basename(name.replace("\\", "/"))
        if safe in ("", ".", ".."):  # '..'가 통과하면 디렉터리 자체가 타겟 — 저장 실패로 레코드 유실
            safe = "attachment"
        dedup, i = safe, 2
        while dedup in used:  # 디스코드 클립보드 이미지는 전부 image.png — 동명 첨부 덮어쓰기 방지
            dedup = f"{i}-{safe}"
            i += 1
        used.add(dedup)
        try:
            (d / dedup).write_bytes(data)
        except Exception:  # 첨부 하나 저장 실패로 파싱된 레코드 전체를 잃으면 안 됨
            links.append(f"(첨부 저장 실패: {dedup})")
            continue
        links.append(f"![[raw/attachments/{rec_id}/{dedup}]]")
    return links


def advance_log(cfg: Config, vcfg: VaultConfig, session: LogSession | None, text: str,
                files: list[tuple[str, bytes]] | None = None,
                ) -> tuple[LogSession | None, list[str]]:
    """log 대화 한 스텝. (다음 세션 또는 None, 회신 메시지들) 반환."""
    files = files or []
    if session is None:
        try:
            parsed = parse_log(cfg, text, vcfg)
        except Exception as e:
            with _VAULT_LOCK:
                path = save_unparsed(cfg.vault, text, str(e))
                save_attachments(cfg.vault, path.stem, files)  # 첨부도 유실 없이 보존
            return None, [f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}"]
        session = LogSession(text=text, parsed=parsed, files=list(files))
    else:
        session.files.extend(files)
        if not text.strip():  # 빈 답변(첨부만 등) — 재파싱 없이 있는 정보로 저장
            return None, finalize_log(cfg, vcfg, session)
        session.text = f"{session.text}\n\n[추가 답변]\n{text}"
        try:
            session.parsed = parse_log(cfg, session.text, vcfg)
        except Exception:
            return None, finalize_log(cfg, vcfg, session)  # 직전 파싱 결과로 저장 진행
    gaps = missing_required(session.parsed, vcfg)
    if gaps and session.rounds < MAX_ROUNDS:
        session.rounds += 1
        qs = "\n".join(f"- {q}" for q in gaps)
        return session, [f"기록 품질을 위해 추가로 알려주세요 (10분 무응답 시 그대로 저장):\n{qs}"]
    return None, finalize_log(cfg, vcfg, session)


def finalize_log(cfg: Config, vcfg: VaultConfig, session: LogSession) -> list[str]:
    """저장 + 첨부만 — 위키 편찬은 absorb_after로 분리 (저장 확인을 즉시 회신하기 위함)."""
    today = _date.today().isoformat()
    with _VAULT_LOCK:
        rec = to_record(cfg.vault, session.parsed, today)
        links = save_attachments(cfg.vault, rec.id, session.files)
        body = session.text + ("\n\n[첨부]\n" + "\n".join(links) if links else "")
        path = save_record(cfg.vault, rec, body, session.parsed.summary)
    msgs = [f"저장됨: `{rec.id}` ({path})\n{session.parsed.summary}".strip()]
    if missing_required(session.parsed, vcfg):
        msgs.append("(일부 필수 정보가 비어 있는 채로 저장됨)")
    return msgs


def absorb_after(cfg: Config) -> list[str]:
    """저장 확인과 분리된 후속 위키 편찬. 갱신 0건이면 조용히 빈 리스트."""
    try:
        with _VAULT_LOCK:
            n = run_absorb(cfg)
        return [f"위키 갱신: {n}건"] if n else []
    except Exception as e:
        return [f"(위키 편찬 실패 — /absorb로 재시도: {e})"]


class HorcruxBot(discord.Client):
    def __init__(self, cfg: Config, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.log_channel = os.environ.get("HORCRUX_LOG_CHANNEL", "실험로그")
        self.ask_channel = os.environ.get("HORCRUX_ASK_CHANNEL", "질문")
        # (channel_id, user_id) → "processing"(LLM 처리 중) | "waiting"(재질문 답변 대기)
        self.busy: dict[tuple[int, int], str] = {}
        self._claimed: set[int] = set()  # wait_for가 소비할 메시지 id — on_message 오탐 방지
        self._synced = False
        self.tree = app_commands.CommandTree(self)
        _register_commands(self)

    async def on_ready(self):
        # 개발 중엔 guild-scoped sync가 즉시 반영 (글로벌은 전파 지연).
        # on_ready는 재연결마다 다시 불림 — sync 반복은 rate limit 위험이라 1회 가드.
        if not self._synced:
            for g in self.guilds:
                self.tree.copy_global_to(guild=g)
                await self.tree.sync(guild=g)
            self._synced = True
        print(f"봇 로그인: {self.user} / 채널 매핑: #{self.log_channel}(log) #{self.ask_channel}(ask)")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.id in self._claimed:
            # wait_for가 소비한 재질문 답변 — dispatch가 wait_for future를 먼저 깨우므로
            # (Python 3.12+에선 _log_flow가 먼저 재개됨) busy 상태만으론 오탐이 남
            self._claimed.discard(message.id)
            return
        key = (message.channel.id, message.author.id)
        state = self.busy.get(key)
        if state == "waiting":
            return  # 대기 중 경합 백스톱
        if state == "processing":
            # LLM 처리 중엔 대기 리스너가 없음 — 무통보 유실 대신 안내
            await self._reply(message, "⏳ 이전 메시지 처리 중 — 끝나면 다시 보내주세요.")
            return
        kind = route(getattr(message.channel, "name", None), self.log_channel, self.ask_channel)
        if kind == "log":
            await self._log_flow(message)
        elif kind == "ask":
            await self._ask_flow(message)

    @staticmethod
    async def _reply(message: discord.Message, text: str) -> None:
        # 원 메시지가 삭제됐으면 reply가 400 (Unknown message) — 채널 전송으로 폴백
        try:
            await message.reply(text)
        except discord.HTTPException:
            await message.channel.send(text)

    async def _send(self, message: discord.Message, msgs: list[str]) -> None:
        # 첫 청크는 원 메시지에 답장(reply) — 다중 유저 채널 귀속 명확 + 작성자 알림
        first = True
        for m in msgs:
            for chunk in split_message(m):
                if first:
                    await self._reply(message, chunk)
                    first = False
                else:
                    await message.channel.send(chunk)

    @staticmethod
    async def _read_files(message: discord.Message) -> list[tuple[str, bytes]]:
        return [(a.filename, await a.read()) for a in message.attachments]

    async def _log_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            if not message.content.strip():
                await self._reply(message, "첨부만으론 기록할 수 없어요 — 텍스트 로그와 함께 보내주세요.")
                return
            # LLM 완료까지 진행률 신호가 없으므로 접수 확인이 유일한 체감 장치
            await self._reply(message, "🔬 로그 분석 중... (수십 초~수 분 걸릴 수 있어요)")
            vcfg = load_vault_config(self.cfg.vault)
            files = await self._read_files(message)
            async with message.channel.typing():
                session, msgs = await asyncio.to_thread(
                    advance_log, self.cfg, vcfg, None, message.content, files)
            await self._send(message, msgs)
            while session:
                def check(m, _a=message.author, _c=message.channel):
                    ok = m.author == _a and m.channel == _c
                    if ok:
                        self._claimed.add(m.id)  # dispatch 시점(동기)에 선점 — on_message 오탐 방지
                    return ok
                self.busy[key] = "waiting"
                try:
                    reply = await self.wait_for("message", check=check, timeout=REPLY_TIMEOUT)
                    self.busy[key] = "processing"
                    await self._reply(reply, "🔬 답변 반영 중...")
                    rfiles = await self._read_files(reply)
                    async with message.channel.typing():
                        session, msgs = await asyncio.to_thread(
                            advance_log, self.cfg, vcfg, session, reply.content, rfiles)
                except asyncio.TimeoutError:
                    self.busy[key] = "processing"
                    await self._reply(message, "⏱ 응답이 없어 있는 정보로 저장합니다...")
                    session, msgs = None, await asyncio.to_thread(
                        finalize_log, self.cfg, vcfg, session)
                await self._send(message, msgs)
            # 저장 확인과 분리된 후속 위키 편찬 (0건이면 조용히 생략)
            wiki_msgs = await asyncio.to_thread(absorb_after, self.cfg)
            await self._send(message, wiki_msgs)
        except Exception as e:
            await self._send(message, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)

    async def _ask_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            if message.attachments:
                await self._reply(message, "(첨부는 진단 분석에 사용되지 않아요 — 텍스트만 참고합니다)")
            if not message.content.strip():
                return
            await self._reply(message, "🔍 과거 기록 검색·진단 중... (수십 초~수 분 걸릴 수 있어요)")
            async with message.channel.typing():
                answer = await asyncio.to_thread(diagnose, self.cfg, message.content)
            await self._send(message, [answer.strip() or "(빈 응답)"])
        except Exception as e:
            await self._send(message, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)


async def _followup(interaction: discord.Interaction, msg: str) -> None:
    try:
        for chunk in split_message(msg):  # 긴 예외 문자열 등 2000자 초과 대비
            await interaction.followup.send(chunk)
    except discord.HTTPException:
        # ponytail: defer 토큰 15분 만료(장시간 /seed·/absorb) 대비 — 채널 전송 폴백
        for chunk in split_message(msg):
            await interaction.channel.send(chunk)


def _register_commands(bot_: HorcruxBot) -> None:
    @bot_.tree.command(name="feedback", description="레코드 해결 여부·실제 원인 기록")
    @app_commands.describe(record_id="레코드 id", resolved="해결 여부",
                           cause="확인된 실제 원인", note="메모")
    async def feedback_cmd(interaction: discord.Interaction, record_id: str,
                           resolved: bool, cause: str | None = None, note: str = ""):
        await interaction.response.defer()
        try:
            msg = await asyncio.to_thread(_locked, run_feedback, bot_.cfg, record_id, resolved, cause, note)
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)

    @bot_.tree.command(name="absorb", description="위키 아티클 편찬 (재시도·수동 실행)")
    async def absorb_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            n = await asyncio.to_thread(_locked, run_absorb, bot_.cfg)  # 락 우회 금지
            msg = f"아티클 갱신: {n}건"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)

    @bot_.tree.command(name="seed", description="합성 데모 데이터 생성")
    @app_commands.describe(n="생성 건수")
    async def seed_cmd(interaction: discord.Interaction, n: int = 6):
        await interaction.response.defer()
        try:
            saved = await asyncio.to_thread(_locked, run_seed, bot_.cfg, n)  # 락 우회 금지
            msg = f"합성 로그 {saved}건 저장 (위키 편찬 포함)"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        await _followup(interaction, msg)


def build_client(cfg: Config) -> HorcruxBot:
    intents = discord.Intents.default()
    intents.message_content = True  # privileged — 개발자 포털에서도 켜야 함
    return HorcruxBot(cfg, intents=intents)


def run_bot(cfg: Config) -> None:
    token = os.environ.get("HORCRUX_DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "HORCRUX_DISCORD_TOKEN 미설정 — Discord 개발자 포털에서 봇 토큰을 발급해 환경변수로 넣어주세요")
    build_client(cfg).run(token)

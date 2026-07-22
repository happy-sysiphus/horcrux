# Horcrux 디스코드 봇 프론트엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 랩서버 상주 디스코드 봇 — 채널 메시지로 log/ask, 슬래시 커맨드로 feedback/absorb/seed.

**Architecture:** 단일 프로세스. 신규 모듈 `src/horcrux/bot.py` 하나에 순수 대화 로직(테스트 대상)과 discord.py 글루를 분리해 담는다. 코어 함수는 기존 시그니처 그대로 재사용, 백엔드 변경은 `run_feedback` 반환값 1건.

**Tech Stack:** Python 3.10+, discord.py ≥2.6, pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-horcrux-discord-bot-design.md`

## Global Constraints

- pytest 실행은 반드시 `python -m pytest -q --basetemp=.pytest_tmp` (샌드박스 temp 권한 문제).
- 테스트에서 LLM·디스코드 네트워크 호출 금지 — 전부 모킹.
- 봇 토큰은 `HORCRUX_DISCORD_TOKEN` 환경변수로만. 코드·레포·테스트에 실제 토큰 금지.
- 채널 이름 기본값: log=`실험로그`, ask=`질문` (env `HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL` 오버라이드).
- 재질문 최대 3회, 응답 대기 타임아웃 600초, 디스코드 메시지 2000자 제한.
- 커밋 메시지는 기존 스타일: `feat:`/`fix:`/`docs:` + 한국어 요약.
- 구현은 워크트리에서 (superpowers:using-git-worktrees — 예: `bot-impl` 브랜치).

---

### Task 1: 백엔드 변경 2건 — `run_feedback` 반환값 + `save_unparsed` 추출

**Files:**
- Modify: `src/horcrux/feedback.py`
- Modify: `src/horcrux/ingest.py` (파싱 실패 needs_review 폴백을 함수로 추출 — CLI·봇 공용, 중복 제거)
- Modify: `src/horcrux/cli.py:50` (feedback 분기)
- Test: `tests/test_feedback.py`, `tests/test_ingest.py`

**Interfaces:**
- Produces: `run_feedback(cfg, record_id, resolved, cause, note) -> str` — 결과 메시지 반환 (봇·CLI 공용).
- Produces: `ingest.save_unparsed(vault, text, err) -> Path` — 파싱 실패 원문을 needs_review로 저장.

- [ ] **Step 1: 기존 테스트를 반환값 검증으로 수정 (실패 확인용)**

`tests/test_feedback.py` 전체를 다음으로 교체:

```python
from horcrux import feedback as fb
from horcrux.config import Config
from horcrux.records import ExperimentRecord, SuspectedCause, load_record, record_path, save_record


def test_run_feedback_updates(tmp_path):
    rec = ExperimentRecord(id="2026-07-19_x-001", date="2026-07-19",
                           suspected_causes=[SuspectedCause(cause="타겟 산화")])
    save_record(tmp_path, rec, "원문", "정리")
    msg = fb.run_feedback(Config(vault=tmp_path), rec.id, True, "타겟 산화", "연마 후 해결")
    assert "해결로 기록됨" in msg and "타겟 산화" in msg
    loaded, _ = load_record(record_path(tmp_path, rec.id))
    assert loaded.resolution.resolved is True
    assert loaded.resolution.actual_cause == "타겟 산화"
    assert loaded.suspected_causes[0].status == "confirmed"


def test_run_feedback_missing_record(tmp_path):
    msg = fb.run_feedback(Config(vault=tmp_path), "없는-id", True, None, "")
    assert "찾을 수 없음" in msg
```

`tests/test_ingest.py` 끝에 추가 (파일 상단 임포트에 `load_record`는 이미 있음):

```python
def test_save_unparsed_preserves_text(tmp_path):
    path = ingest.save_unparsed(tmp_path, "원문 로그", "boom")
    rec, body = load_record(path)
    assert rec.needs_review is True
    assert "원문 로그" in body
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_feedback.py tests/test_ingest.py`
Expected: FAIL — `run_feedback`이 `None` 반환이라 TypeError, `save_unparsed`는 AttributeError.

- [ ] **Step 3: 구현**

`src/horcrux/feedback.py`의 `run_feedback`을 다음으로 교체:

```python
def run_feedback(cfg: Config, record_id: str, resolved: bool, cause: str | None, note: str) -> str:
    if not record_path(cfg.vault, record_id).exists():
        return f"레코드를 찾을 수 없음: {record_id}"
    rec = update_resolution(cfg.vault, record_id, resolved, cause, note)
    state = "해결" if resolved else "미해결"
    return f"{rec.id}: {state}로 기록됨" + (f" (원인: {cause})" if cause else "")
```

`src/horcrux/cli.py`의 feedback 분기를 print 감싸기로 수정:

```python
    elif args.cmd == "feedback":
        from .feedback import run_feedback
        print(run_feedback(cfg, args.record_id, args.resolved == "y", args.cause, args.note))
```

`src/horcrux/ingest.py`에 함수 추가 (`run_log` 위 — 필요한 이름들은 이미 임포트돼 있음):

```python
def save_unparsed(vault: Path, text: str, err: str) -> Path:
    """파싱 실패 원문을 needs_review로 보존 — CLI·봇 공용 (데이터 유실 방지)."""
    today = _date.today().isoformat()
    rec = ExperimentRecord(id=make_record_id(vault, today, "exp"), date=today, needs_review=True)
    return save_record(vault, rec, text, f"(자동 파싱 실패: {err})")
```

`run_log`의 except 블록을 이 함수 사용으로 교체:

```python
    except Exception as e:
        path = save_unparsed(cfg.vault, text, str(e))
        print(f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}")
        return path
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_feedback.py tests/test_ingest.py tests/test_cli.py`
Expected: PASS 전부.

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/feedback.py src/horcrux/ingest.py src/horcrux/cli.py tests/test_feedback.py tests/test_ingest.py
git commit -m "feat: run_feedback 메시지 반환·save_unparsed 추출 (봇 공용 준비)"
```

---

### Task 2: bot.py 순수 대화 로직 (세션 상태 머신 + 메시지 분할)

**Files:**
- Modify: `pyproject.toml` (dependencies에 discord.py 추가)
- Create: `src/horcrux/bot.py`
- Create: `tests/test_bot.py`

**Interfaces:**
- Consumes: `ingest.parse_log(cfg, text, vcfg) -> ParsedLog`, `ingest.missing_required(parsed, vcfg) -> list[str]`, `ingest.to_record(vault, parsed, date) -> ExperimentRecord`, `ingest.save_unparsed(vault, text, err) -> Path` (Task 1), `records.save_record(vault, rec, text, summary) -> Path`, `absorb.run_absorb(cfg) -> int`
- Produces: `LogSession` (dataclass: `text: str`, `parsed: ParsedLog`, `rounds: int`), `advance_log(cfg, vcfg, session: LogSession | None, text: str) -> tuple[LogSession | None, list[str]]`, `finalize_log(cfg, vcfg, session: LogSession) -> list[str]`, `split_message(text: str, limit: int = 2000) -> list[str]`, `route(channel_name: str | None, log_channel: str, ask_channel: str) -> str | None` (`"log"`/`"ask"`/`None`)

- [ ] **Step 1: 의존성 추가 + 설치**

`pyproject.toml`의 `dependencies` 배열에 `"discord.py>=2.6"` 추가 (기존 pydantic·pyyaml 줄 옆).

Run: `pip install -e .`
Expected: discord.py 2.6 이상 설치 (현재 최신 2.7.x — 버전 문자열에 얽매이지 말 것). 확인: `python -c "import discord; print(discord.__version__)"`

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_bot.py` 생성:

```python
import pytest

from horcrux import bot
from horcrux.bot import LogSession, advance_log, finalize_log, route, split_message
from horcrux.config import Config, VaultConfig
from horcrux.ingest import ParsedLog
from horcrux.records import Parameter, Symptom

VC = VaultConfig(
    required_fields=["objective", "parameters", "results", "symptom", "actions_taken"],
    required_parameters=[],
)


def full_parsed():
    return ParsedLog(
        experiment_type="박막 증착", objective="ITO 증착",
        parameters=[Parameter(name="RF power", value="150W")],
        results="증착률 5nm/min", summary="정리 서술",
        symptom=Symptom(category="none", description="문제 없음"),
    )


def cfg(tmp_path):
    return Config(vault=tmp_path, provider="claude")


def saved_files(tmp_path):
    d = tmp_path / "raw" / "experiments"
    return list(d.glob("*.md")) if d.exists() else []


# --- split_message ---

def test_split_message_short():
    assert split_message("짧은 답") == ["짧은 답"]


def test_split_message_long():
    chunks = split_message("가" * 4500)
    assert [len(c) for c in chunks] == [2000, 2000, 500]
    assert "".join(chunks) == "가" * 4500


def test_split_message_empty():
    assert split_message("") == []


# --- route (채널 매핑 분기) ---

def test_route_channel_mapping():
    assert route("실험로그", "실험로그", "질문") == "log"
    assert route("질문", "실험로그", "질문") == "ask"
    assert route("잡담", "실험로그", "질문") is None
    assert route(None, "실험로그", "질문") is None  # DM 등 이름 없는 채널


# --- advance_log / finalize_log ---

def test_advance_log_complete_saves_and_absorbs(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: full_parsed())
    monkeypatch.setattr(bot, "run_absorb", lambda c: 2)
    session, msgs = advance_log(cfg(tmp_path), VC, None, "완결 로그 원문")
    assert session is None
    joined = "\n".join(msgs)
    assert "저장됨" in joined and "위키 갱신: 2건" in joined
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_gaps_asks_question(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())  # 전부 빈 필드
    session, msgs = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    assert session is not None and session.rounds == 1
    assert "알려주세요" in msgs[0]
    assert saved_files(tmp_path) == []  # 아직 저장 안 됨


def test_advance_log_round_cap_saves_after_three(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())  # 계속 빈 필드
    monkeypatch.setattr(bot, "run_absorb", lambda c: 0)
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    for expected_round in (2, 3):
        session, msgs = advance_log(cfg(tmp_path), VC, session, "여전히 빈약")
        assert session is not None and session.rounds == expected_round
    session, msgs = advance_log(cfg(tmp_path), VC, session, "마지막도 빈약")  # 4번째 → 저장
    assert session is None
    joined = "\n".join(msgs)
    assert "저장됨" in joined and "일부 필수 정보" in joined
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_empty_reply_skips_reparse(monkeypatch, tmp_path):
    calls = []

    def fake(c, t, v):
        calls.append(t)
        return ParsedLog()

    monkeypatch.setattr(bot, "parse_log", fake)
    monkeypatch.setattr(bot, "run_absorb", lambda c: 0)
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")
    session, msgs = advance_log(cfg(tmp_path), VC, session, "   ")  # 빈 답변 (첨부만 등)
    assert session is None
    assert len(calls) == 1  # 재파싱 없이 있는 정보로 저장
    assert "저장됨" in "\n".join(msgs)
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_parse_failure_saves_needs_review(monkeypatch, tmp_path):
    def boom(c, t, v):
        raise RuntimeError("CLI 실패")
    monkeypatch.setattr(bot, "parse_log", boom)
    session, msgs = advance_log(cfg(tmp_path), VC, None, "원문")
    assert session is None
    assert "needs_review" in msgs[0]
    assert len(saved_files(tmp_path)) == 1


def test_advance_log_continue_parse_failure_finalizes_previous(monkeypatch, tmp_path):
    monkeypatch.setattr(bot, "run_absorb", lambda c: 0)
    monkeypatch.setattr(bot, "parse_log", lambda c, t, v: ParsedLog())
    session, _ = advance_log(cfg(tmp_path), VC, None, "빈약한 로그")

    def boom(c, t, v):
        raise RuntimeError("재파싱 실패")
    monkeypatch.setattr(bot, "parse_log", boom)
    session, msgs = advance_log(cfg(tmp_path), VC, session, "추가 답변")
    assert session is None
    assert "저장됨" in "\n".join(msgs)  # 직전 파싱 결과로 저장 진행
    assert len(saved_files(tmp_path)) == 1


def test_finalize_absorb_failure_warns_but_saves(monkeypatch, tmp_path):
    def boom(c):
        raise RuntimeError("편찬 실패")
    monkeypatch.setattr(bot, "run_absorb", boom)
    session = LogSession(text="원문", parsed=full_parsed(), rounds=0)
    msgs = finalize_log(cfg(tmp_path), VC, session)
    joined = "\n".join(msgs)
    assert "저장됨" in joined and "위키 편찬 실패" in joined
    assert len(saved_files(tmp_path)) == 1
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: FAIL — 수집 단계 임포트 에러 `ImportError: cannot import name 'bot' from 'horcrux'` (from-임포트라 ModuleNotFoundError가 아님)

- [ ] **Step 4: 구현 — bot.py 순수 로직 부분**

`src/horcrux/bot.py` 생성 (이 태스크에서는 순수 로직까지만 — 글루는 Task 3):

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from .absorb import run_absorb
from .config import Config, VaultConfig
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .records import save_record

MAX_ROUNDS = 3       # 재질문 최대 횟수
REPLY_TIMEOUT = 600  # 재질문 응답 대기 (초)
MSG_LIMIT = 2000     # 디스코드 메시지 길이 제한


@dataclass
class LogSession:
    text: str          # 누적 원문 (원본 + 추가 답변)
    parsed: ParsedLog
    rounds: int = 0    # 지금까지 던진 재질문 횟수


def split_message(text: str, limit: int = MSG_LIMIT) -> list[str]:
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def route(channel_name: str | None, log_channel: str, ask_channel: str) -> str | None:
    """채널 이름 → 처리 종류. 매핑 밖 채널·DM은 None (무시)."""
    if channel_name == log_channel:
        return "log"
    if channel_name == ask_channel:
        return "ask"
    return None


def advance_log(cfg: Config, vcfg: VaultConfig, session: LogSession | None,
                text: str) -> tuple[LogSession | None, list[str]]:
    """log 대화 한 스텝. (다음 세션 또는 None, 회신 메시지들) 반환."""
    if session is None:
        try:
            parsed = parse_log(cfg, text, vcfg)
        except Exception as e:
            path = save_unparsed(cfg.vault, text, str(e))
            return None, [f"파싱에 실패해 원문만 저장했습니다 (needs_review): {path}"]
        session = LogSession(text=text, parsed=parsed)
    else:
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
    today = _date.today().isoformat()
    rec = to_record(cfg.vault, session.parsed, today)
    path = save_record(cfg.vault, rec, session.text, session.parsed.summary)
    msgs = [f"저장됨: `{rec.id}` ({path})\n{session.parsed.summary}".strip()]
    if missing_required(session.parsed, vcfg):
        msgs.append("(일부 필수 정보가 비어 있는 채로 저장됨)")
    try:
        n = run_absorb(cfg)
        msgs.append(f"위키 갱신: {n}건")
    except Exception as e:
        msgs.append(f"(위키 편찬 실패 — /absorb로 재시도: {e})")
    return msgs
```

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: PASS 전부 (11개).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/horcrux/bot.py tests/test_bot.py
git commit -m "feat: 봇 순수 대화 로직 — log 세션 상태 머신·메시지 분할"
```

---

### Task 3: 디스코드 글루 — HorcruxBot 클라이언트 + 슬래시 커맨드

**Files:**
- Modify: `src/horcrux/bot.py` (글루 추가)
- Test: `tests/test_bot.py` (오프라인 구성 테스트 추가)

**Interfaces:**
- Consumes: Task 2의 `advance_log`/`finalize_log`/`split_message`, `diagnose.diagnose(cfg, text) -> str`, `feedback.run_feedback(...) -> str` (Task 1), `seed.run_seed(cfg, n) -> int`
- Produces: `build_client(cfg: Config) -> HorcruxBot` (연결 없이 구성 가능 — 테스트 대상), `run_bot(cfg: Config) -> None` (토큰 검사 후 `client.run(token)`)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_bot.py` 끝에 추가:

```python
# --- 디스코드 글루 (오프라인 구성 검증) ---

def test_build_client_registers_commands(tmp_path):
    c = bot.build_client(cfg(tmp_path))
    assert {cmd.name for cmd in c.tree.get_commands()} == {"feedback", "absorb", "seed"}
    assert c.intents.message_content is True


def test_run_bot_without_token_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("HORCRUX_DISCORD_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HORCRUX_DISCORD_TOKEN"):
        bot.run_bot(cfg(tmp_path))
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: 신규 2개 FAIL — `AttributeError: module 'horcrux.bot' has no attribute 'build_client'`

- [ ] **Step 3: 구현 — 글루 추가**

`src/horcrux/bot.py` 상단 임포트에 추가 (Task 2에서 만든 임포트 아래):

```python
import asyncio
import os

import discord
from discord import app_commands

from .config import load_vault_config   # 기존 .config 임포트 줄에 이름만 추가해도 됨
from .diagnose import diagnose
from .feedback import run_feedback
from .seed import run_seed
```

파일 끝에 글루 추가:

```python
class HorcruxBot(discord.Client):
    def __init__(self, cfg: Config, **kwargs):
        super().__init__(**kwargs)
        self.cfg = cfg
        self.log_channel = os.environ.get("HORCRUX_LOG_CHANNEL", "실험로그")
        self.ask_channel = os.environ.get("HORCRUX_ASK_CHANNEL", "질문")
        # (channel_id, user_id) → "processing"(LLM 처리 중) | "waiting"(재질문 답변 대기)
        self.busy: dict[tuple[int, int], str] = {}
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
        key = (message.channel.id, message.author.id)
        state = self.busy.get(key)
        if state == "waiting":
            return  # 재질문 답변 — wait_for가 소비
        if state == "processing":
            # LLM 처리 중엔 대기 리스너가 없음 — 무통보 유실 대신 안내
            await message.channel.send("⏳ 이전 메시지 처리 중 — 끝나면 다시 보내주세요.")
            return
        kind = route(getattr(message.channel, "name", None), self.log_channel, self.ask_channel)
        if kind == "log":
            await self._log_flow(message)
        elif kind == "ask":
            await self._ask_flow(message)

    async def _send(self, channel, msgs: list[str]) -> None:
        for m in msgs:
            for chunk in split_message(m):
                await channel.send(chunk)

    async def _log_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            vcfg = load_vault_config(self.cfg.vault)
            async with message.channel.typing():
                session, msgs = await asyncio.to_thread(
                    advance_log, self.cfg, vcfg, None, message.content)
            await self._send(message.channel, msgs)
            while session:
                def check(m, _a=message.author, _c=message.channel):
                    return m.author == _a and m.channel == _c
                self.busy[key] = "waiting"
                try:
                    reply = await self.wait_for("message", check=check, timeout=REPLY_TIMEOUT)
                    self.busy[key] = "processing"
                    async with message.channel.typing():
                        session, msgs = await asyncio.to_thread(
                            advance_log, self.cfg, vcfg, session, reply.content)
                except asyncio.TimeoutError:
                    self.busy[key] = "processing"
                    session, msgs = None, await asyncio.to_thread(
                        finalize_log, self.cfg, vcfg, session)
                await self._send(message.channel, msgs)
        except Exception as e:
            await self._send(message.channel, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)

    async def _ask_flow(self, message: discord.Message) -> None:
        key = (message.channel.id, message.author.id)
        self.busy[key] = "processing"
        try:
            async with message.channel.typing():
                answer = await asyncio.to_thread(diagnose, self.cfg, message.content)
            await self._send(message.channel, [answer])
        except Exception as e:
            await self._send(message.channel, [f"⚠ 오류: {e}"])
        finally:
            self.busy.pop(key, None)


def _register_commands(bot_: HorcruxBot) -> None:
    @bot_.tree.command(name="feedback", description="레코드 해결 여부·실제 원인 기록")
    @app_commands.describe(record_id="레코드 id", resolved="해결 여부",
                           cause="확인된 실제 원인", note="메모")
    async def feedback_cmd(interaction: discord.Interaction, record_id: str,
                           resolved: bool, cause: str | None = None, note: str = ""):
        await interaction.response.defer()
        try:
            msg = await asyncio.to_thread(run_feedback, bot_.cfg, record_id, resolved, cause, note)
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        for chunk in split_message(msg):  # 긴 예외 문자열 등 2000자 초과 대비
            await interaction.followup.send(chunk)

    @bot_.tree.command(name="absorb", description="위키 아티클 편찬 (재시도·수동 실행)")
    async def absorb_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            n = await asyncio.to_thread(run_absorb, bot_.cfg)
            msg = f"아티클 갱신: {n}건"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        for chunk in split_message(msg):  # 긴 예외 문자열 등 2000자 초과 대비
            await interaction.followup.send(chunk)

    @bot_.tree.command(name="seed", description="합성 데모 데이터 생성")
    @app_commands.describe(n="생성 건수")
    async def seed_cmd(interaction: discord.Interaction, n: int = 6):
        await interaction.response.defer()
        try:
            saved = await asyncio.to_thread(run_seed, bot_.cfg, n)
            msg = f"합성 로그 {saved}건 저장 (위키 편찬 포함)"
        except Exception as e:
            msg = f"⚠ 오류: {e}"
        for chunk in split_message(msg):  # 긴 예외 문자열 등 2000자 초과 대비
            await interaction.followup.send(chunk)


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
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_bot.py`
Expected: PASS 전부 (13개).

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/bot.py tests/test_bot.py
git commit -m "feat: 디스코드 글루 — 채널 매핑 log/ask 흐름·슬래시 커맨드 3종"
```

---

### Task 4: CLI `horcrux bot` 서브커맨드

**Files:**
- Modify: `src/horcrux/cli.py`
- Test: `tests/test_cli.py` (기존 파일 끝에 추가)

**Interfaces:**
- Consumes: `bot.run_bot(cfg)` (Task 3)

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_cli.py` 끝에 추가:

```python
def test_cli_bot_dispatch(monkeypatch):
    called = {}
    import horcrux.bot as bot_mod
    monkeypatch.setattr(bot_mod, "run_bot", lambda cfg: called.setdefault("cfg", cfg))
    from horcrux.cli import main
    main(["bot"])
    assert "cfg" in called
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: 신규 1개 FAIL — `bot` 서브커맨드 없어 argparse가 SystemExit(2).

- [ ] **Step 3: 구현**

`src/horcrux/cli.py`에 서브파서 추가 (seed 파서 아래):

```python
    sub.add_parser("bot", help="디스코드 봇 실행")
```

분기 추가 (seed 분기 아래):

```python
    elif args.cmd == "bot":
        from . import bot
        bot.run_bot(cfg)
```

주의: `from .bot import run_bot`이 아니라 `from . import bot` 후 `bot.run_bot(cfg)` — 테스트의 monkeypatch가 모듈 속성을 바꾸므로 모듈 경유 호출이어야 반영된다.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest -q --basetemp=.pytest_tmp tests/test_cli.py`
Expected: PASS 전부.

- [ ] **Step 5: Commit**

```bash
git add src/horcrux/cli.py tests/test_cli.py
git commit -m "feat: horcrux bot 서브커맨드"
```

---

### Task 5: 문서 — AGENTS.md 레이어 경계 + README 봇 섹션

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`

- [ ] **Step 1: AGENTS.md에 경계 섹션 추가**

`AGENTS.md` 끝에 추가:

```markdown
## 레이어 소유 경계 (병렬 작업 시)

| 영역 | 소유 파일 |
|---|---|
| 프론트 (디스코드 봇) | `src/horcrux/bot.py`, `tests/test_bot.py` |
| 백엔드 (코어) | `src/horcrux/{ingest,diagnose,retrieval,absorb,feedback,records,llm,config,seed}.py` + 기존 테스트 |
| 공용 접점 | `cli.py`, `pyproject.toml`, `README.md`, `docs/**` |

프론트가 의존하는 백엔드 인터페이스(전체 목록):
`parse_log(cfg, text, vcfg)` · `missing_required(parsed, vcfg)` · `to_record(vault, parsed, date)` ·
`save_record(vault, rec, text, summary)` · `save_unparsed(vault, text, err)` · `load_vault_config(vault)` ·
`diagnose(cfg, text)` · `run_absorb(cfg)` · `run_feedback(cfg, id, resolved, cause, note) -> str` ·
`run_seed(cfg, n)`.
시그니처 변경은 백엔드 먼저 수정 후 프론트가 따라간다 — 같은 파일 동시 수정 금지.
```

- [ ] **Step 2: README에 봇 섹션 추가**

`README.md` 설치 섹션 아래에 추가:

```markdown
## 디스코드 봇

봇 프로세스를 랩서버에 상주시키면 연구원은 디스코드 채널로 기록·질의한다.

### 준비 (1회)

1. [Discord 개발자 포털](https://discord.com/developers/applications) → New Application → Bot 추가
2. **Privileged Gateway Intents에서 Message Content Intent 켜기** (필수)
3. Bot 토큰 발급 → 환경변수 `HORCRUX_DISCORD_TOKEN`으로 설정 (레포·코드에 넣지 말 것)
4. OAuth2 → URL Generator에서 `bot` 스코프 + 권한(View Channels, Send Messages, Read Message History) 체크 → 생성된 URL로 서버에 초대
5. 서버에 텍스트 채널 `실험로그`, `질문` 생성 (이름 변경 시 `HORCRUX_LOG_CHANNEL`/`HORCRUX_ASK_CHANNEL`)

### 실행

```bash
horcrux bot
```

- `#실험로그`에 자연어 로그를 쓰면 구조화 저장 (부족 정보는 봇이 되물음 — 10분 무응답 시 그대로 저장)
- `#질문`에 문제를 쓰면 과거 사례·위키 기반 진단
- `/feedback` `/absorb` `/seed` 슬래시 커맨드 지원
- 랩서버에도 선택한 LLM CLI(claude 등)가 설치·로그인돼 있어야 한다
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: 봇 설정·실행 가이드 + 레이어 소유 경계"
```

---

### Task 6: 전체 검증 + 수동 스모크

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트**

Run: `python -m pytest -q --basetemp=.pytest_tmp`
Expected: 전부 PASS (기존 61 + 신규 ≈15).

- [ ] **Step 2: 수동 스모크 (사용자 개입 필요 — 토큰·서버 준비는 README 절차)**

1. `$env:HORCRUX_DISCORD_TOKEN="<토큰>"; horcrux bot` — "봇 로그인" 출력 확인
2. `#실험로그`에 일부러 빈약한 로그 입력 → 재질문 확인 → 답변 → "저장됨"(경로 포함) + 위키 갱신 확인
3. LLM 처리 중 같은 채널에 연속 메시지 → "⏳ 이전 메시지 처리 중" 안내 확인
4. 매핑 밖 채널(예: #잡담)에 메시지 → 봇 무반응 확인
5. `#질문`에 문제 입력 → 사례 인용 답변 확인
6. `/feedback record_id:<위 id> resolved:True cause:테스트` → "해결로 기록됨" 확인

- [ ] **Step 3: 브랜치 마무리**

superpowers:finishing-a-development-branch 스킬로 main 병합·정리.

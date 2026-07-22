from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

from .absorb import run_absorb
from .config import Config, VaultConfig
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .records import save_record

MAX_ROUNDS = 3       # 재질문 최대 횟수
REPLY_TIMEOUT = 600  # 재질문 응답 대기 (초)
MSG_LIMIT = 2000     # 디스코드 메시지 길이 제한

# ponytail: 전역 볼트 쓰기 락 — 동시 저장 시 record id 순번 경쟁(덮어쓰기)·
# _absorb_log.json 경쟁 방지. 처리량이 문제되면 볼트별 락으로 세분화.
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
    for name, data in files:
        safe = os.path.basename(name.replace("\\", "/"))
        if safe in ("", ".", ".."):  # '..'가 통과하면 디렉터리 자체가 타겟 — 저장 실패로 레코드 유실
            safe = "attachment"
        (d / safe).write_bytes(data)
        links.append(f"![[raw/attachments/{rec_id}/{safe}]]")
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

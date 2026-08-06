from __future__ import annotations

from .config import Config
from .records import record_path, update_resolution


def run_feedback(cfg: Config, record_id: str, resolved: bool, cause: str | None, note: str) -> str:
    try:
        found = record_path(cfg.vault, record_id).exists()
    except ValueError as e:
        return str(e)          # CLI에 트레이스백 대신 메시지
    if not found:
        return f"레코드를 찾을 수 없음: {record_id}"
    rec = update_resolution(cfg.vault, record_id, resolved, cause, note)
    state = "해결" if resolved else "미해결"
    return f"{rec.id}: {state}로 기록됨" + (f" (원인: {cause})" if cause else "")

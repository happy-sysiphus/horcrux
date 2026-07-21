from __future__ import annotations

from .config import Config
from .records import record_path, update_resolution


def run_feedback(cfg: Config, record_id: str, resolved: bool, cause: str | None, note: str) -> None:
    if not record_path(cfg.vault, record_id).exists():
        print(f"레코드를 찾을 수 없음: {record_id}")
        return
    rec = update_resolution(cfg.vault, record_id, resolved, cause, note)
    state = "해결" if resolved else "미해결"
    print(f"{rec.id}: {state}로 기록됨" + (f" (원인: {cause})" if cause else ""))

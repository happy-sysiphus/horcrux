from __future__ import annotations

import threading
from datetime import date as _date
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .absorb import run_absorb
from .config import Config, load_vault_config
from .diagnose import diagnose_data
from .feedback import run_feedback
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .records import list_records, load_record, record_path, save_record

# ponytail: 전역 볼트 쓰기 락 — 저장 id 순번 경쟁 방지 (로컬 단일 사용자)
_VAULT_LOCK = threading.Lock()

_META_KEYS = ("id", "date", "experiment_type", "objective", "equipment", "materials",
              "symptom", "resolution", "needs_review", "followup_of")


class ParseIn(BaseModel):
    text: str


class RecordIn(BaseModel):
    text: str
    parsed: ParsedLog
    followup_of: str | None = None


class RawIn(BaseModel):
    text: str


class AskIn(BaseModel):
    text: str


class FeedbackIn(BaseModel):
    record_id: str
    resolved: bool
    cause: str | None = None
    note: str = ""


def _absorb_quietly(cfg: Config) -> None:
    try:
        with _VAULT_LOCK:
            run_absorb(cfg)
    except Exception as e:  # 저장은 이미 확정 — absorb 실패는 로그만 (CLI와 동일 정책)
        print(f"(위키 편찬 실패 — 'horcrux absorb'로 재시도: {e})")


def _meta(rec) -> dict:
    d = rec.model_dump()
    return {k: d[k] for k in _META_KEYS}


def create_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="LAB GENE")

    @app.post("/api/parse")
    def api_parse(inp: ParseIn):
        vcfg = load_vault_config(cfg.vault)
        parsed = parse_log(cfg, inp.text, vcfg)
        return {"parsed": parsed.model_dump(), "gaps": missing_required(parsed, vcfg)}

    @app.post("/api/records")
    def api_save(inp: RecordIn, bg: BackgroundTasks):
        today = _date.today().isoformat()
        with _VAULT_LOCK:
            rec = to_record(cfg.vault, inp.parsed, today)
            rec.followup_of = inp.followup_of
            path = save_record(cfg.vault, rec, inp.text, inp.parsed.summary)
        bg.add_task(_absorb_quietly, cfg)
        return {"id": rec.id, "path": str(path)}

    @app.post("/api/records/raw")
    def api_save_raw(inp: RawIn):
        with _VAULT_LOCK:
            path = save_unparsed(cfg.vault, inp.text, "웹에서 파싱 반복 실패")
        return {"id": path.stem, "path": str(path)}

    @app.post("/api/ask")
    def api_ask(inp: AskIn):
        return diagnose_data(cfg, inp.text)

    @app.get("/api/records")
    def api_list():
        out = []
        for p in list_records(cfg.vault):
            try:
                rec, _ = load_record(p)
            except Exception:
                continue  # 손상 md 스킵 — retrieval과 동일 정책
            out.append(_meta(rec))
        out.sort(key=lambda m: m["id"], reverse=True)
        return {"records": out}

    @app.get("/api/records/{record_id}")
    def api_detail(record_id: str):
        p = record_path(cfg.vault, record_id)
        if not p.exists():
            raise HTTPException(404, f"레코드 없음: {record_id}")
        rec, body = load_record(p)
        return {"record": rec.model_dump(), "body": body}

    @app.post("/api/feedback")
    def api_feedback(inp: FeedbackIn):
        if not record_path(cfg.vault, inp.record_id).exists():
            raise HTTPException(404, f"레코드 없음: {inp.record_id}")
        with _VAULT_LOCK:
            msg = run_feedback(cfg, inp.record_id, inp.resolved, inp.cause, inp.note)
        return {"message": msg}

    @app.get("/api/config")
    def api_config():
        vcfg = load_vault_config(cfg.vault)
        return {"required_fields": vcfg.required_fields,
                "required_parameters": vcfg.required_parameters,
                "provider": cfg.provider, "vault": str(cfg.vault)}

    # 소스 체크아웃(-e 설치) 기준 경로 — 1차 데모 전제. wheel/exe 배포는 2차에서 패키지 데이터로 포함
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if dist.exists():  # 빌드 전엔 API만 (개발은 vite dev + proxy)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def run_serve(cfg: Config, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn
    uvicorn.run(create_app(cfg), host=host, port=port)

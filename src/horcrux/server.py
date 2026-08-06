from __future__ import annotations

import os
import threading
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date as _date
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .absorb import run_absorb
from .auth import AuthCtx, verify_token
from .config import Config, load_vault_config
from .diagnose import diagnose_data
from .feedback import run_feedback
from .ingest import ParsedLog, missing_required, parse_log, save_unparsed, to_record
from .labs import LabsDB
from .records import list_records, load_record, record_path, save_record

_META_KEYS = ("id", "date", "experiment_type", "objective", "equipment", "materials",
              "symptom", "resolution", "needs_review", "followup_of")


@dataclass
class DeployCtx:
    db: object          # LabsDB (테스트는 FakeDB)
    jwt_secret: str
    data_dir: Path


def load_deploy_ctx() -> DeployCtx | None:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        return None
    return DeployCtx(
        db=LabsDB(url, os.environ["SUPABASE_SERVICE_KEY"],
                  os.environ["CRED_ENCRYPTION_KEY"]),
        jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
    )


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


class LabIn(BaseModel):
    name: str


class JoinIn(BaseModel):
    invite_code: str


class SettingsIn(BaseModel):
    name: str | None = None
    daily_llm_limit: int | None = None
    llm_mode: str | None = None          # 'central'로 되돌리기
    llm_provider: str | None = None      # own 등록: 'claude' | 'api'
    llm_credential: str | None = None    # own 등록: 평문 토큰/키 (서버가 암호화)
    rotate_invite: bool = False


def _absorb_quietly(cfg: Config, lock: threading.Lock) -> None:
    try:
        with lock:
            run_absorb(cfg)
    except Exception as e:  # 저장은 이미 확정 — absorb 실패는 로그만 (CLI와 동일 정책)
        print(f"(위키 편찬 실패 — 'horcrux absorb'로 재시도: {e})")


def _meta(rec) -> dict:
    d = rec.model_dump()
    return {k: d[k] for k in _META_KEYS}


def create_app(cfg: Config, deploy: DeployCtx | None = None) -> FastAPI:
    app = FastAPI(title="LAB GENE")

    # ponytail: 볼트별 쓰기 락 — 로컬 모드는 키 "local" 하나만 사용 (기존과 동일 동작)
    _locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def get_ctx(authorization: str | None = Header(default=None)) -> AuthCtx | None:
        if deploy is None:
            return None                       # 로컬 모드 — 인증 없음
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "로그인이 필요합니다")
        try:
            user_id = verify_token(authorization.removeprefix("Bearer "), deploy.jwt_secret)
        except ValueError:
            raise HTTPException(401, "토큰이 유효하지 않습니다")
        found = deploy.db.lab_for_user(user_id)
        if found is None:
            return AuthCtx(user_id=user_id, lab=None, role=None)
        return AuthCtx(user_id=user_id, lab=found[0], role=found[1])

    def require_lab(ctx: AuthCtx | None = Depends(get_ctx)) -> AuthCtx | None:
        if deploy is not None and (ctx is None or ctx.lab is None):
            raise HTTPException(403, "소속 연구실이 없습니다 — 연구실을 만들거나 초대 코드로 합류하세요")
        return ctx

    def lab_cfg(ctx: AuthCtx | None) -> Config:
        if deploy is None or ctx is None:
            return cfg
        lab = ctx.lab
        vault = deploy.data_dir / "vaults" / lab["id"]
        if lab["llm_mode"] == "own":
            cred = deploy.db.get_credential(lab["id"])
            if cred is None:
                raise HTTPException(502, "연구실 LLM 크레덴셜이 없습니다 — 관리자에게 재등록을 요청하세요")
            provider, secret = cred
            if provider == "claude":
                return replace(cfg, vault=vault, provider="claude",
                               extra_env={"CLAUDE_CODE_OAUTH_TOKEN": secret})
            return replace(cfg, vault=vault, provider="api", api_key=secret)
        return replace(cfg, vault=vault, provider="api", api_key=None)  # 중앙 키(env)

    def lab_lock(ctx: AuthCtx | None) -> threading.Lock:
        return _locks[ctx.lab["id"] if (deploy and ctx and ctx.lab) else "local"]

    def check_usage(ctx: AuthCtx | None) -> None:
        if deploy is None or ctx is None:
            return
        if not deploy.db.bump_usage(ctx.lab["id"], ctx.lab["daily_llm_limit"]):
            raise HTTPException(429, "오늘 사용량 한도를 초과했습니다 — 관리자에게 문의하세요")

    @app.post("/api/parse")
    def api_parse(inp: ParseIn, ctx=Depends(require_lab)):
        check_usage(ctx)
        c = lab_cfg(ctx)
        vcfg = load_vault_config(c.vault)
        parsed = parse_log(c, inp.text, vcfg)
        return {"parsed": parsed.model_dump(), "gaps": missing_required(parsed, vcfg)}

    @app.post("/api/records")
    def api_save(inp: RecordIn, bg: BackgroundTasks, ctx=Depends(require_lab)):
        check_usage(ctx)
        c = lab_cfg(ctx)
        today = _date.today().isoformat()
        with lab_lock(ctx):
            rec = to_record(c.vault, inp.parsed, today)
            rec.followup_of = inp.followup_of
            path = save_record(c.vault, rec, inp.text, inp.parsed.summary)
        bg.add_task(_absorb_quietly, c, lab_lock(ctx))
        return {"id": rec.id, "path": str(path)}

    @app.post("/api/records/raw")
    def api_save_raw(inp: RawIn, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        with lab_lock(ctx):
            path = save_unparsed(c.vault, inp.text, "웹에서 파싱 반복 실패")
        return {"id": path.stem, "path": str(path)}

    @app.post("/api/ask")
    def api_ask(inp: AskIn, ctx=Depends(require_lab)):
        check_usage(ctx)
        c = lab_cfg(ctx)
        return diagnose_data(c, inp.text)

    @app.get("/api/records")
    def api_list(ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        out = []
        for p in list_records(c.vault):
            try:
                rec, _ = load_record(p)
            except Exception:
                continue  # 손상 md 스킵 — retrieval과 동일 정책
            out.append(_meta(rec))
        out.sort(key=lambda m: m["id"], reverse=True)
        return {"records": out}

    @app.get("/api/records/{record_id}")
    def api_detail(record_id: str, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        p = record_path(c.vault, record_id)
        if not p.exists():
            raise HTTPException(404, f"레코드 없음: {record_id}")
        rec, body = load_record(p)
        return {"record": rec.model_dump(), "body": body}

    @app.post("/api/feedback")
    def api_feedback(inp: FeedbackIn, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        if not record_path(c.vault, inp.record_id).exists():
            raise HTTPException(404, f"레코드 없음: {inp.record_id}")
        with lab_lock(ctx):
            msg = run_feedback(c, inp.record_id, inp.resolved, inp.cause, inp.note)
        return {"message": msg}

    @app.get("/api/config")
    def api_config(ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        vcfg = load_vault_config(c.vault)
        return {"required_fields": vcfg.required_fields,
                "required_parameters": vcfg.required_parameters,
                "provider": c.provider, "vault": str(c.vault)}

    @app.post("/api/labs")
    def api_lab_create(inp: LabIn, ctx=Depends(get_ctx)):
        if deploy is None:
            raise HTTPException(404)
        if ctx.lab is not None:
            raise HTTPException(409, "이미 소속 연구실이 있습니다")
        lab = deploy.db.create_lab(ctx.user_id, inp.name)
        (deploy.data_dir / "vaults" / lab["id"]).mkdir(parents=True, exist_ok=True)
        return {"lab": lab, "role": "admin"}

    @app.post("/api/labs/join")
    def api_lab_join(inp: JoinIn, ctx=Depends(get_ctx)):
        if deploy is None:
            raise HTTPException(404)
        if ctx.lab is not None:
            raise HTTPException(409, "이미 소속 연구실이 있습니다")
        try:
            lab = deploy.db.join_lab(ctx.user_id, inp.invite_code)
        except LookupError:
            raise HTTPException(404, "초대 코드가 올바르지 않습니다")
        return {"lab": lab, "role": "member"}

    @app.get("/api/labs/me")
    def api_lab_me(ctx=Depends(require_lab)):
        return {"lab": ctx.lab, "role": ctx.role} if ctx else {"lab": None, "role": None}

    @app.put("/api/labs/settings")
    def api_lab_settings(inp: SettingsIn, ctx=Depends(require_lab)):
        if deploy is None:
            raise HTTPException(404)
        if ctx.role != "admin":
            raise HTTPException(403, "관리자만 설정을 변경할 수 있습니다")
        if inp.llm_credential and inp.llm_provider:
            deploy.db.set_credential(ctx.lab["id"], inp.llm_provider, inp.llm_credential)
        fields = {}
        if inp.name: fields["name"] = inp.name
        if inp.daily_llm_limit: fields["daily_llm_limit"] = inp.daily_llm_limit
        if inp.llm_mode: fields["llm_mode"] = inp.llm_mode
        if inp.rotate_invite:
            from .labs import new_invite_code
            fields["invite_code"] = new_invite_code()
        if fields:
            deploy.db.update_settings(ctx.lab["id"], fields)
        return {"ok": True}

    # 소스 체크아웃(-e 설치) 기준 경로 — 1차 데모 전제. wheel/exe 배포는 2차에서 패키지 데이터로 포함
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if dist.exists():  # 빌드 전엔 API만 (개발은 vite dev + proxy)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def run_serve(cfg: Config, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn
    uvicorn.run(create_app(cfg, load_deploy_ctx()), host=host, port=port)

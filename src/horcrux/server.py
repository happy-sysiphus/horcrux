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
from .records import Reference, list_records, load_record, record_path, save_record, write_md

_META_KEYS = ("id", "date", "experiment_type", "objective", "equipment", "materials",
              "symptom", "resolution", "needs_review", "followup_of", "references")


@dataclass
class DeployCtx:
    db: object          # LabsDB (테스트는 FakeDB)
    jwt_secret: str
    data_dir: Path
    jwks_url: str | None = None   # 신형 Supabase(ES256 서명)의 공개 키 목록


def load_deploy_ctx() -> DeployCtx | None:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        return None
    return DeployCtx(
        db=LabsDB(url, os.environ["SUPABASE_SERVICE_KEY"],
                  os.environ["CRED_ENCRYPTION_KEY"]),
        jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
        jwks_url=f"{url}/auth/v1/.well-known/jwks.json",
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


class ReferencesIn(BaseModel):
    references: list[Reference]


class LabIn(BaseModel):
    name: str


class JoinIn(BaseModel):
    invite_code: str


class SettingsIn(BaseModel):
    # daily_llm_limit은 일부러 없다 — 일일 상한은 서비스 운영자만 정한다(DB에서 직접).
    # 연구실 관리자가 자기 상한을 올릴 수 있으면 중앙 API 키 비용을 통제할 수 없다.
    name: str | None = None
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


def _existing_record(vault: Path, record_id: str) -> Path:
    """볼트 안의 실재 레코드 경로. 없거나 id가 부정하면 404 (트레이스백 노출 금지)."""
    try:
        p = record_path(vault, record_id)
    except ValueError:
        raise HTTPException(404, f"레코드 없음: {record_id}") from None
    if not p.exists():
        raise HTTPException(404, f"레코드 없음: {record_id}")
    return p


def _lab_out(lab: dict | None, role: str | None) -> dict | None:
    """클라이언트에 나가는 연구실 필드 화이트리스트 — llm_credential은 절대 포함하지 않는다."""
    if lab is None:
        return None
    out = {k: lab.get(k) for k in ("id", "name", "llm_mode", "llm_provider", "daily_llm_limit")}
    if role == "admin":
        out["invite_code"] = lab.get("invite_code")
    return out


def create_app(cfg: Config, deploy: DeployCtx | None = None) -> FastAPI:
    app = FastAPI(title="LAB GENE")

    # ponytail: 볼트별 쓰기 락 — 로컬 모드는 키 "local" 하나만 사용 (기존과 동일 동작)
    _locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def get_ctx(authorization: str | None = Header(default=None)) -> AuthCtx | None:
        if deploy is None:
            return None                       # 로컬 모드 — 인증 없음
        if not authorization or not authorization.startswith("Bearer "):
            print("(401: Authorization 헤더 없음)")
            raise HTTPException(401, "로그인이 필요합니다")
        try:
            user_id = verify_token(authorization.removeprefix("Bearer "),
                                   deploy.jwt_secret, deploy.jwks_url)
        except ValueError as e:
            print(f"(401: {e})")   # 파일럿 진단용 — 검증 실패 사유가 없으면 원인 추적 불가
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
        rec, body = load_record(_existing_record(c.vault, record_id))
        return {"record": rec.model_dump(), "body": body}

    @app.post("/api/feedback")
    def api_feedback(inp: FeedbackIn, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        _existing_record(c.vault, inp.record_id)
        with lab_lock(ctx):
            msg = run_feedback(c, inp.record_id, inp.resolved, inp.cause, inp.note)
        return {"message": msg}

    @app.put("/api/records/{record_id}/references")
    def api_put_references(record_id: str, inp: ReferencesIn, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        p = _existing_record(c.vault, record_id)
        with lab_lock(ctx):
            rec, body = load_record(p)
            rec.references = inp.references
            write_md(p, rec.model_dump(), body)  # body 보존 — update_resolution과 동일
        return {"record": _meta(rec)}

    @app.get("/api/auth-config")
    def api_auth_config():
        # 유일한 무인증 엔드포인트 — 프론트가 로그인 전에 Supabase를 초기화해야 한다.
        # anon key는 브라우저에 노출되는 것이 전제인 공개 값(RLS가 실제 방어).
        return {"deploy": deploy is not None,
                "supabase_url": os.environ.get("SUPABASE_URL"),
                "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY")}

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
        return {"lab": _lab_out(lab, "admin"), "role": "admin"}

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
        return {"lab": _lab_out(lab, "member"), "role": "member"}

    @app.get("/api/labs/me")
    def api_lab_me(ctx=Depends(get_ctx)):
        # require_lab이 아니라 get_ctx — 무소속도 200(lab=null)으로 답해야
        # 프론트가 "온보딩 필요"와 "서버 오류"를 구분한다
        if ctx is None or ctx.lab is None:
            return {"lab": None, "role": None, "usage_today": 0}
        out = {"lab": _lab_out(ctx.lab, ctx.role), "role": ctx.role,
               "usage_today": deploy.db.get_usage(ctx.lab["id"])}
        if ctx.role == "admin":
            out["members"] = deploy.db.list_members(ctx.lab["id"])
        return out

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
        if inp.llm_mode: fields["llm_mode"] = inp.llm_mode
        if inp.rotate_invite:
            from .labs import new_invite_code
            fields["invite_code"] = new_invite_code()
        if fields:
            deploy.db.update_settings(ctx.lab["id"], fields)
        return {"ok": True}

    # 기본은 소스 체크아웃(-e 설치) 기준 경로. 비편집 설치(Docker)는 HORCRUX_WEB_DIST로 지정
    dist = Path(os.environ.get("HORCRUX_WEB_DIST")
                or Path(__file__).resolve().parents[2] / "web" / "dist")
    if dist.exists():  # 빌드 전엔 API만 (개발은 vite dev + proxy)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


def run_serve(cfg: Config, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn
    from .backup import start_backup_thread

    deploy = load_deploy_ctx()
    if deploy is not None:
        start_backup_thread(deploy)
    uvicorn.run(create_app(cfg, deploy), host=host, port=port)

# 배포·멀티테넌시·인증 백엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** horcrux 서버를 Railway+Supabase 기반 멀티테넌트 서비스로 — 연구실별 볼트 격리, Supabase 인증, 중앙/자기 크레덴셜 LLM, 사용량 상한, 일일 백업, 봇 제거.

**Architecture:** 배포 모드는 옵트인 — `SUPABASE_URL` 환경변수가 있으면 JWT 인증 + 연구실 컨텍스트로 동작하고, 없으면 기존 로컬 단일 볼트 동작 그대로(로컬 개발·CLI·기존 테스트 보존). 코어(ingest/retrieval/absorb 등)는 무수정 — `Config`가 요청별로 만들어질 뿐. 신규 모듈 3개(auth/labs/backup)로 격리.

**Tech Stack:** FastAPI, supabase-py(v2), PyJWT, cryptography(Fernet), anthropic SDK, Docker.

**스펙:** `docs/superpowers/specs/2026-08-06-deployment-auth-design.md`

## Global Constraints

- 워크트리: `backend-polish`, 브랜치 `backend`, 커밋마다 `git push origin backend`
- 테스트 실행: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp` (둘 다 필수 — editable install이 main을 가리킴)
- 모든 파일 I/O `encoding="utf-8"` 명시 (Windows cp949)
- 단위 테스트는 LLM·Supabase 호출 없이 통과 (전부 모킹)
- 커밋 트레일러: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 배포 의존성은 optional extra `deploy`로 격리 — 로컬 `pip install -e .` 무영향
- 사용량 카운트 단위: LLM 유발 API 요청 1건 = 1 (parse/ask/records) — 스펙의 "호출 1회"를 요청 단위로 단순화, 기본 한도 200/일 (Task 9에서 스펙에 반영)
- 서버 env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`, `ANTHROPIC_API_KEY`, `HORCRUX_MODEL`, `CRED_ENCRYPTION_KEY`, `DATA_DIR`(기본 `/data`)

---

### Task 1: 디스코드 봇 제거

**Files:**
- Delete: `src/horcrux/bot.py`, `tests/test_bot.py`(존재 시)
- Modify: `pyproject.toml`(discord.py 제거), `src/horcrux/cli.py`(bot 분기·init의 디스코드 항목), `src/horcrux/config.py`(discord_token·log_channel·ask_channel 필드), `README.md`(봇 절 삭제)
- Test: 기존 스위트 통과가 검증

**Interfaces:**
- Produces: `Config`는 `vault/provider/model`만 남음(+Task 3·4에서 필드 추가). `load_config`/`save_config`/`run_init`에서 디스코드 키 제거.

- [ ] **Step 1: 삭제·수정**

`bot.py` 삭제. `pyproject.toml` dependencies에서 `"discord.py>=2.6"` 제거. `config.py`의 `Config`에서 `discord_token/log_channel/ask_channel` 필드와 `load_config`의 해당 pick 3줄 제거. `cli.py`에서 `sub.add_parser("bot", ...)`·`elif args.cmd == "bot":` 분기 제거, `run_init`에서 토큰·채널 질문 3개와 저장 키 제거(남는 항목: vault/provider/model). README에서 봇 관련 절 삭제. `grep -ri discord src tests README.md`로 잔재 0 확인.

- [ ] **Step 2: 테스트 전체 실행**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS (bot 관련 테스트가 있었다면 함께 삭제)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: 디스코드 봇 제거 — 웹 프론트로 대체" && git push origin backend
```

---

### Task 2: llm.py — `api` provider (anthropic SDK, 중앙 모드)

**Files:**
- Modify: `src/horcrux/llm.py`, `src/horcrux/config.py`, `pyproject.toml`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: 기존 `generate(cfg, system, user)` / `generate_parsed(cfg, system, user, schema)`
- Produces: `Config.api_key: str | None = None` 필드. `cfg.provider == "api"`면 anthropic SDK 호출(키 = `cfg.api_key` 또는 env `ANTHROPIC_API_KEY`). `PROVIDERS = ("claude", "gemini", "codex", "api")`. generate_parsed는 provider 무관 공통 경로(JSON 지시+검증+1회 재시도) 유지.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_llm.py`에 추가

```python
def test_generate_api_provider(monkeypatch):
    calls = {}

    class FakeMsg:
        content = [type("B", (), {"type": "text", "text": "응답"})()]

    class FakeClient:
        def __init__(self, api_key):
            calls["key"] = api_key
            self.messages = type("M", (), {"create": self._create})()

        def _create(self, **kw):
            calls["kw"] = kw
            return FakeMsg()

    import horcrux.llm as llm_mod
    monkeypatch.setattr(llm_mod, "_anthropic_client", lambda key: FakeClient(key))
    out = generate(Config(vault="v", provider="api", model="claude-sonnet-4-5",
                          api_key="sk-test"), "시스템", "유저")
    assert out == "응답"
    assert calls["key"] == "sk-test"
    assert calls["kw"]["system"] == "시스템"


def test_generate_api_without_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        generate(Config(vault="v", provider="api"), "s", "u")
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_llm.py -k api_provider -v`
Expected: FAIL (`api` 미지원 NotImplementedError)

- [ ] **Step 3: 구현** — `config.py`의 `Config`에 `api_key: str | None = None` 추가. `llm.py`:

```python
PROVIDERS = ("claude", "gemini", "codex", "api")
_API_DEFAULT_MODEL = "claude-sonnet-4-5"


def _anthropic_client(api_key: str):
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _generate_api(cfg: Config, system: str, user: str) -> str:
    key = cfg.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("api provider에는 ANTHROPIC_API_KEY(또는 연구실 키)가 필요합니다")
    resp = _anthropic_client(key).messages.create(
        model=cfg.model or _API_DEFAULT_MODEL, max_tokens=16000,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return next(b.text for b in resp.content if b.type == "text").strip()
```

`generate()` 분기 맨 앞에 `if cfg.provider == "api": return _generate_api(cfg, system, user)` 추가 (프롬프트 결합 전 — api는 system 파라미터 분리 전달). `pyproject.toml`에 `deploy = ["anthropic", "supabase", "PyJWT", "cryptography"]` extra 신설, `dev` extra에 `"anthropic"` 대신 전부 모킹이므로 추가 불필요 — 단 import가 함수 안이라 미설치 환경 테스트도 통과.

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: llm에 api provider — 중앙 ANTHROPIC_API_KEY 모드" && git push origin backend
```

---

### Task 3: llm.py — 연구실 크레덴셜 env 주입 (own 모드)

**Files:**
- Modify: `src/horcrux/llm.py`, `src/horcrux/config.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `Config.extra_env: dict[str, str] | None = None`. CLI provider 호출 시 `subprocess` env에 병합(`{**os.environ, **extra_env}`). own-claude 모드는 서버가 `extra_env={"CLAUDE_CODE_OAUTH_TOKEN": <복호화 토큰>}`으로 Config를 만든다.

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_run_merges_extra_env(monkeypatch):
    captured = {}

    class P:
        pid = 1
        returncode = 0
        def communicate(self, prompt=None, timeout=None):
            return "ok", ""

    def fake_popen(cmd, **kw):
        captured["env"] = kw.get("env")
        return P()

    monkeypatch.setattr(llm.subprocess, "Popen", fake_popen)
    llm._run(["x"], "p", env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"})
    assert captured["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    assert "PATH" in captured["env"]  # os.environ 병합 확인


def test_generate_passes_extra_env(fake_run):
    generate(Config(vault="v", provider="claude",
                    extra_env={"CLAUDE_CODE_OAUTH_TOKEN": "tok"}), "s", "u")
    # fake_run이 (cmd, prompt, env) 3-튜플을 기록하도록 FakeRunFn.__call__ 시그니처에 env=None 추가
    assert fake_run.calls[0][2] == {"CLAUDE_CODE_OAUTH_TOKEN": "tok"}
```

(기존 `FakeRunFn.__call__(self, cmd, prompt)`를 `(self, cmd, prompt, env=None)`로 바꾸고 `calls.append((cmd, prompt, env))` — 기존 assert는 인덱스 유지라 무수정.)

- [ ] **Step 2: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_llm.py -k extra_env -v`
Expected: FAIL (TypeError: unexpected keyword 'env')

- [ ] **Step 3: 구현** — `config.py`의 `Config`에 `extra_env: dict[str, str] | None = None` 추가. `llm.py`의 `_run` 시그니처를 `_run(cmd, prompt, env=None)`로, Popen에 `env={**os.environ, **env} if env else None` 전달. `generate()`의 CLI 세 분기 `_run(...)` 호출에 `env=cfg.extra_env` 전달.

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: llm CLI 호출에 연구실별 크레덴셜 env 주입" && git push origin backend
```

---

### Task 4: labs.py — Supabase DB 래퍼 + 크레덴셜 암호화

**Files:**
- Create: `src/horcrux/labs.py`, `tests/test_labs.py`, `db/schema.sql`

**Interfaces:**
- Consumes: supabase-py `create_client(url, key)` — 테스트는 전부 페이크 클라이언트
- Produces:

```python
class LabsDB:
    def __init__(self, url: str, service_key: str, fernet_key: str): ...
    def create_lab(self, user_id: str, name: str) -> dict        # {id,name,invite_code,...} admin 등록 포함
    def join_lab(self, user_id: str, invite_code: str) -> dict   # 없는 코드면 LookupError
    def lab_for_user(self, user_id: str) -> tuple[dict, str] | None  # (lab row, role)
    def update_settings(self, lab_id: str, fields: dict) -> None # name/daily_llm_limit/llm_mode/invite_code
    def set_credential(self, lab_id: str, provider: str, secret: str) -> None  # Fernet 암호화 저장
    def get_credential(self, lab_id: str) -> tuple[str, str] | None            # (provider, 평문) 복호화
    def bump_usage(self, lab_id: str, limit: int) -> bool        # 오늘 카운트+1, 초과면 False
def new_invite_code() -> str                                     # secrets.token_hex(4) 8자
```

- [ ] **Step 1: `db/schema.sql` 작성** (Supabase SQL 에디터에서 수동 1회 실행 — 파일럿 규모라 마이그레이션 도구 없음)

```sql
create table labs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  invite_code text unique not null,
  created_by uuid not null,
  llm_mode text not null default 'central',   -- 'central' | 'own'
  llm_provider text,                          -- own: 'claude' | 'api'
  llm_credential text,                        -- Fernet 암호문
  daily_llm_limit int not null default 200,
  created_at timestamptz default now()
);
create table lab_members (
  lab_id uuid references labs(id),
  user_id uuid not null,
  role text not null default 'member',        -- 'admin' | 'member'
  primary key (lab_id, user_id)
);
create table llm_usage (
  lab_id uuid references labs(id),
  day date not null,
  count int not null default 0,
  primary key (lab_id, day)
);
```

- [ ] **Step 2: 실패 테스트 작성** — `tests/test_labs.py`. supabase 클라이언트를 인메모리 페이크로:

```python
import pytest
from cryptography.fernet import Fernet

from horcrux import labs as labs_mod
from horcrux.labs import LabsDB, new_invite_code


class FakeTable:
    def __init__(self, store, name):
        self.store, self.name = store, name
        self._filters, self._payload, self._op = {}, None, None

    def insert(self, row):  self._op, self._payload = "insert", row; return self
    def update(self, row):  self._op, self._payload = "update", row; return self
    def upsert(self, row):  self._op, self._payload = "upsert", row; return self
    def select(self, *_):   self._op = self._op or "select"; return self
    def eq(self, k, v):     self._filters[k] = v; return self

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        if self._op == "insert":
            rows.append(dict(self._payload)); return type("R", (), {"data": [rows[-1]]})
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        if self._op == "update":
            for r in matched: r.update(self._payload)
        if self._op == "upsert":
            if matched: matched[0].update(self._payload)
            else: rows.append(dict(self._payload)); matched = [rows[-1]]
        return type("R", (), {"data": matched})


class FakeClient:
    def __init__(self):
        self.store = {}
    def table(self, name):
        return FakeTable(self.store, name)


@pytest.fixture
def db(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(labs_mod, "create_client", lambda url, key: fake)
    d = LabsDB("http://x", "svc", Fernet.generate_key().decode())
    d._fake = fake
    return d


def test_create_lab_registers_admin(db):
    lab = db.create_lab("user-1", "산화막랩")
    assert len(lab["invite_code"]) == 8
    assert db.lab_for_user("user-1") == (lab, "admin")


def test_join_lab_by_code_and_bad_code(db):
    lab = db.create_lab("user-1", "랩")
    db.join_lab("user-2", lab["invite_code"])
    assert db.lab_for_user("user-2")[1] == "member"
    with pytest.raises(LookupError):
        db.join_lab("user-3", "nope0000")


def test_credential_roundtrip_encrypted(db):
    lab = db.create_lab("u", "랩")
    db.set_credential(lab["id"], "claude", "secret-token")
    stored = db._fake.store["labs"][0]["llm_credential"]
    assert "secret-token" not in stored           # 평문 저장 금지
    assert db.get_credential(lab["id"]) == ("claude", "secret-token")


def test_bump_usage_enforces_limit(db):
    lab = db.create_lab("u", "랩")
    assert db.bump_usage(lab["id"], limit=2) is True
    assert db.bump_usage(lab["id"], limit=2) is True
    assert db.bump_usage(lab["id"], limit=2) is False   # 3회째 = 초과
```

- [ ] **Step 3: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_labs.py -v`
Expected: FAIL (ModuleNotFoundError: horcrux.labs)

- [ ] **Step 4: 구현** — `src/horcrux/labs.py`:

```python
from __future__ import annotations

import datetime
import secrets

from cryptography.fernet import Fernet

try:
    from supabase import create_client
except ModuleNotFoundError:      # deploy extra 미설치 로컬 — LabsDB 생성 시점에만 필요
    create_client = None


def new_invite_code() -> str:
    return secrets.token_hex(4)


class LabsDB:
    def __init__(self, url: str, service_key: str, fernet_key: str):
        self._c = create_client(url, service_key)
        self._fernet = Fernet(fernet_key.encode())

    def create_lab(self, user_id: str, name: str) -> dict:
        row = {"name": name, "invite_code": new_invite_code(), "created_by": user_id}
        lab = self._c.table("labs").insert(row).execute().data[0]
        self._c.table("lab_members").insert(
            {"lab_id": lab["id"], "user_id": user_id, "role": "admin"}).execute()
        return lab

    def join_lab(self, user_id: str, invite_code: str) -> dict:
        found = self._c.table("labs").select("*").eq("invite_code", invite_code).execute().data
        if not found:
            raise LookupError("초대 코드가 올바르지 않습니다")
        lab = found[0]
        self._c.table("lab_members").insert(
            {"lab_id": lab["id"], "user_id": user_id, "role": "member"}).execute()
        return lab

    def lab_for_user(self, user_id: str) -> tuple[dict, str] | None:
        ms = self._c.table("lab_members").select("*").eq("user_id", user_id).execute().data
        if not ms:
            return None
        labs = self._c.table("labs").select("*").eq("id", ms[0]["lab_id"]).execute().data
        return labs[0], ms[0]["role"]

    def update_settings(self, lab_id: str, fields: dict) -> None:
        self._c.table("labs").update(fields).eq("id", lab_id).execute()

    def set_credential(self, lab_id: str, provider: str, secret: str) -> None:
        enc = self._fernet.encrypt(secret.encode()).decode()
        self.update_settings(lab_id, {"llm_mode": "own", "llm_provider": provider,
                                      "llm_credential": enc})

    def get_credential(self, lab_id: str) -> tuple[str, str] | None:
        labs = self._c.table("labs").select("*").eq("id", lab_id).execute().data
        if not labs or not labs[0].get("llm_credential"):
            return None
        return labs[0]["llm_provider"], self._fernet.decrypt(
            labs[0]["llm_credential"].encode()).decode()

    def bump_usage(self, lab_id: str, limit: int) -> bool:
        day = datetime.date.today().isoformat()
        rows = (self._c.table("llm_usage").select("*")
                .eq("lab_id", lab_id).eq("day", day).execute().data)
        count = (rows[0]["count"] if rows else 0) + 1
        if count > limit:
            return False
        self._c.table("llm_usage").upsert(
            {"lab_id": lab_id, "day": day, "count": count}).execute()
        return True
```

(참고: bump_usage는 read-then-write라 동시 요청에 근사 카운트 — `# ponytail: 정확 카운트 필요하면 postgres rpc increment로 교체` 주석을 코드에 남긴다.)

- [ ] **Step 5: 통과 확인 + 전체 스위트**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS (cryptography는 dev 의존성에 추가: pyproject `dev` extra에 `"cryptography"`)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: labs — Supabase 연구실 DB 래퍼·크레덴셜 암호화·사용량 카운트" && git push origin backend
```

---

### Task 5: auth.py — Supabase JWT 검증

**Files:**
- Create: `src/horcrux/auth.py`, `tests/test_auth.py`

**Interfaces:**
- Produces:

```python
@dataclass
class AuthCtx:
    user_id: str
    lab: dict | None      # 무소속이면 None
    role: str | None      # 'admin' | 'member' | None

def verify_token(token: str, jwt_secret: str) -> str
    # HS256 검증 → sub(user_id). 실패 시 ValueError
```

`verify_token`은 PyJWT `jwt.decode(token, jwt_secret, algorithms=["HS256"], audience="authenticated")`. (Supabase 신규 프로젝트가 비대칭 키면 legacy HS256 secret을 프로젝트 설정에서 발급받아 쓴다 — README 배포 절에 명시, Task 8.)

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_auth.py`:

```python
import jwt as pyjwt
import pytest

from horcrux.auth import verify_token

SECRET = "test-secret"


def make_token(sub="user-1", secret=SECRET, aud="authenticated", **extra):
    return pyjwt.encode({"sub": sub, "aud": aud, **extra}, secret, algorithm="HS256")


def test_verify_token_returns_user_id():
    assert verify_token(make_token(), SECRET) == "user-1"


def test_verify_token_rejects_bad_signature():
    with pytest.raises(ValueError):
        verify_token(make_token(secret="wrong"), SECRET)


def test_verify_token_rejects_expired():
    tok = make_token(exp=0)
    with pytest.raises(ValueError):
        verify_token(tok, SECRET)
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_auth.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 구현** — `src/horcrux/auth.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import jwt


@dataclass
class AuthCtx:
    user_id: str
    lab: dict | None
    role: str | None


def verify_token(token: str, jwt_secret: str) -> str:
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"],
                             audience="authenticated")
    except jwt.PyJWTError as e:
        raise ValueError(f"토큰 검증 실패: {e}") from None
    return payload["sub"]
```

(PyJWT를 `dev` extra에도 추가.)

- [ ] **Step 4: 통과 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: auth — Supabase JWT 검증" && git push origin backend
```

---

### Task 6: server.py — 배포 모드 배선 (인증·연구실 컨텍스트·상한·신규 API)

**Files:**
- Modify: `src/horcrux/server.py`
- Test: `tests/test_server_deploy.py` (신규 — 기존 `tests/test_server.py`는 로컬 모드 회귀 검증으로 무수정 통과해야 함)

**Interfaces:**
- Consumes: `LabsDB`(Task 4), `verify_token`·`AuthCtx`(Task 5), `Config(api_key, extra_env)`(Task 2·3)
- Produces:

```python
@dataclass
class DeployCtx:
    db: LabsDB
    jwt_secret: str
    data_dir: Path

def create_app(cfg: Config, deploy: DeployCtx | None = None) -> FastAPI
def load_deploy_ctx() -> DeployCtx | None   # SUPABASE_URL 없으면 None
```

신규 엔드포인트: `POST /api/labs` {name}, `POST /api/labs/join` {invite_code}, `GET /api/labs/me`, `PUT /api/labs/settings` {name?, daily_llm_limit?, llm_mode?, llm_provider?, llm_credential?, rotate_invite?}.
동작 규칙: 배포 모드에서 기존 엔드포인트는 인증 필수 + lab 필수(무소속 403). LLM 유발 3종(parse/ask/records)은 요청당 `bump_usage` — 초과 시 429. 볼트 락은 lab_id별.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_server_deploy.py`:

```python
import threading
from dataclasses import dataclass
from pathlib import Path

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from horcrux import server
from horcrux.config import Config
from horcrux.server import DeployCtx, create_app

SECRET = "s"


def tok(sub="user-1"):
    return pyjwt.encode({"sub": sub, "aud": "authenticated"}, SECRET, algorithm="HS256")


class FakeDB:
    def __init__(self):
        self.labs, self.members, self.usage_ok = {}, {}, True
        self.credentials = {}

    def create_lab(self, user_id, name):
        lab = {"id": f"lab-{len(self.labs)+1}", "name": name, "invite_code": "abcd1234",
               "llm_mode": "central", "llm_provider": None, "daily_llm_limit": 200}
        self.labs[lab["id"]] = lab
        self.members[user_id] = (lab["id"], "admin")
        return lab

    def join_lab(self, user_id, code):
        for lab in self.labs.values():
            if lab["invite_code"] == code:
                self.members[user_id] = (lab["id"], "member")
                return lab
        raise LookupError("bad code")

    def lab_for_user(self, user_id):
        if user_id not in self.members:
            return None
        lab_id, role = self.members[user_id]
        return self.labs[lab_id], role

    def update_settings(self, lab_id, fields):
        self.labs[lab_id].update(fields)

    def get_credential(self, lab_id):
        return self.credentials.get(lab_id)

    def set_credential(self, lab_id, provider, secret):
        self.credentials[lab_id] = (provider, secret)
        self.labs[lab_id].update({"llm_mode": "own", "llm_provider": provider})

    def bump_usage(self, lab_id, limit):
        return self.usage_ok


@pytest.fixture
def deploy_client(tmp_path):
    db = FakeDB()
    app = create_app(Config(vault=tmp_path / "unused"),
                     DeployCtx(db=db, jwt_secret=SECRET, data_dir=tmp_path))
    return TestClient(app), db


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_requires_token(deploy_client):
    client, _ = deploy_client
    assert client.get("/api/records").status_code == 401


def test_no_lab_403_and_onboarding(deploy_client):
    client, db = deploy_client
    assert client.get("/api/records", headers=auth(tok())).status_code == 403
    r = client.post("/api/labs", json={"name": "랩"}, headers=auth(tok()))
    assert r.status_code == 200
    assert client.get("/api/records", headers=auth(tok())).status_code == 200


def test_join_by_invite_code(deploy_client):
    client, db = deploy_client
    client.post("/api/labs", json={"name": "랩"}, headers=auth(tok("u1")))
    r = client.post("/api/labs/join", json={"invite_code": "abcd1234"}, headers=auth(tok("u2")))
    assert r.status_code == 200
    me = client.get("/api/labs/me", headers=auth(tok("u2"))).json()
    assert me["role"] == "member"


def test_vault_isolated_per_lab(deploy_client, tmp_path):
    client, db = deploy_client
    client.post("/api/labs", json={"name": "A"}, headers=auth(tok("u1")))
    lab_id = db.members["u1"][0]
    # 서버가 이 연구실 요청에 쓰는 볼트 경로 검증: parse를 모킹해 cfg.vault 캡처
    seen = {}
    def fake_parse(cfg, text, vcfg):
        seen["vault"] = cfg.vault
        from horcrux.ingest import ParsedLog
        return ParsedLog()
    import horcrux.server as sv
    orig = sv.parse_log
    sv.parse_log = fake_parse
    try:
        client.post("/api/parse", json={"text": "x"}, headers=auth(tok("u1")))
    finally:
        sv.parse_log = orig
    assert seen["vault"] == tmp_path / "vaults" / lab_id


def test_usage_limit_429(deploy_client):
    client, db = deploy_client
    client.post("/api/labs", json={"name": "랩"}, headers=auth(tok()))
    db.usage_ok = False
    r = client.post("/api/ask", json={"text": "q"}, headers=auth(tok()))
    assert r.status_code == 429


def test_settings_admin_only(deploy_client):
    client, db = deploy_client
    client.post("/api/labs", json={"name": "랩"}, headers=auth(tok("u1")))
    client.post("/api/labs/join", json={"invite_code": "abcd1234"}, headers=auth(tok("u2")))
    assert client.put("/api/labs/settings", json={"name": "새이름"},
                      headers=auth(tok("u2"))).status_code == 403
    assert client.put("/api/labs/settings", json={"name": "새이름"},
                      headers=auth(tok("u1"))).status_code == 200
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_server_deploy.py -v`
Expected: FAIL (ImportError: DeployCtx)

- [ ] **Step 3: 구현** — `server.py` 리팩터:

```python
from collections import defaultdict
from dataclasses import dataclass, replace
import os

from fastapi import Depends, Header

from .auth import AuthCtx, verify_token
from .labs import LabsDB


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
```

`create_app(cfg, deploy=None)` 내부:

```python
    _locks: dict[str, threading.Lock] = defaultdict(threading.Lock)  # 로컬 모드 키 "local"

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
```

기존 엔드포인트 수정 패턴 (전부 동일 — `ctx=Depends(require_lab)` 추가, `cfg`→`lab_cfg(ctx)`, `_VAULT_LOCK`→`lab_lock(ctx)`, LLM 유발 3종은 첫 줄에 `check_usage(ctx)`):

```python
    @app.post("/api/parse")
    def api_parse(inp: ParseIn, ctx=Depends(require_lab)):
        check_usage(ctx)
        c = lab_cfg(ctx)
        vcfg = load_vault_config(c.vault)
        parsed = parse_log(c, inp.text, vcfg)
        return {"parsed": parsed.model_dump(), "gaps": missing_required(parsed, vcfg)}
```

신규 엔드포인트:

```python
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
```

`run_serve`는 `create_app(cfg, load_deploy_ctx())`로. `/api/config`는 로컬 모드 전용 정보라 배포 모드에선 lab_cfg 기반으로 동작(vault 경로는 lab별).

- [ ] **Step 4: 통과 확인 + 기존 test_server.py 회귀**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS — 기존 `test_server.py`(deploy=None 경로) 무수정 통과가 핵심 회귀 기준

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: server 배포 모드 — JWT 인증·연구실 컨텍스트·사용량 상한·labs API" && git push origin backend
```

---

### Task 7: backup.py — 일일 볼트 백업

**Files:**
- Create: `src/horcrux/backup.py`, `tests/test_backup.py`
- Modify: `src/horcrux/server.py`(run_serve에서 시작)

**Interfaces:**
- Produces: `make_backup_zip(data_dir: Path) -> Path`(vaults 전체 zip, 임시 파일), `upload_backup(storage, zip_path: Path) -> None`, `start_backup_thread(deploy: DeployCtx, interval_sec: int = 86400) -> threading.Thread`(데몬 스레드, 실패는 print 후 다음 주기).

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_backup.py`:

```python
from horcrux.backup import make_backup_zip
import zipfile


def test_make_backup_zip_contains_vault_files(tmp_path):
    v = tmp_path / "vaults" / "lab-1" / "raw" / "experiments"
    v.mkdir(parents=True)
    (v / "r.md").write_text("내용", encoding="utf-8")
    z = make_backup_zip(tmp_path)
    names = zipfile.ZipFile(z).namelist()
    assert "vaults/lab-1/raw/experiments/r.md" in names
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp tests/test_backup.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 구현** — `src/horcrux/backup.py`:

```python
from __future__ import annotations

import tempfile
import threading
import time
import zipfile
from datetime import date
from pathlib import Path


def make_backup_zip(data_dir: Path) -> Path:
    out = Path(tempfile.mkdtemp()) / f"vaults-{date.today().isoformat()}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((data_dir / "vaults").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(data_dir).as_posix())
    return out


def upload_backup(storage, zip_path: Path) -> None:
    # storage = supabase client.storage.from_("vault-backups")
    storage.upload(zip_path.name, zip_path.read_bytes(),
                   {"content-type": "application/zip", "upsert": "true"})


def start_backup_thread(deploy, interval_sec: int = 86400) -> threading.Thread:
    def loop():
        while True:
            time.sleep(interval_sec)
            try:
                z = make_backup_zip(deploy.data_dir)
                upload_backup(deploy.db._c.storage.from_("vault-backups"), z)
                print(f"백업 업로드: {z.name}")
            except Exception as e:   # 백업 실패는 서비스 영향 없음 — 다음 주기 재시도
                print(f"(백업 실패 — 다음 주기 재시도: {e})")

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
```

`run_serve`: `deploy = load_deploy_ctx()`; `if deploy: start_backup_thread(deploy)`; `uvicorn.run(create_app(cfg, deploy), ...)`.

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: 일일 볼트 백업 — zip 후 Supabase Storage 업로드" && git push origin backend
```

---

### Task 8: Dockerfile + 배포 문서

**Files:**
- Create: `Dockerfile`, `.dockerignore`
- Modify: `README.md`(배포 절), `pyproject.toml`(deploy extra 확정)

**Interfaces:**
- Consumes: `horcrux serve`가 `PORT` env 대응 필요 → `cli.py`의 serve 기본 port를 `int(os.environ.get("PORT", 8765))`로.

- [ ] **Step 1: Dockerfile 작성**

```dockerfile
FROM python:3.12-slim

# claude CLI (연구실 own-claude 모드용) — node 20
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY web/dist ./web/dist
RUN pip install --no-cache-dir ".[web,deploy]"

ENV DATA_DIR=/data
EXPOSE 8765
CMD ["horcrux", "serve", "--host", "0.0.0.0"]
```

`.dockerignore`: `.git`, `.claude`, `.pytest_tmp`, `web/node_modules`, `web/src`, `example-vault`, `tests`, `docs`.

- [ ] **Step 2: cli.py serve PORT 대응**

`sv.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))` (cli.py 상단 `import os` 추가).

- [ ] **Step 3: 로컬 도커 빌드 검증** (도커 없으면 스킵하고 커밋 메시지에 미검증 명시)

Run: `docker build -t horcrux . && docker run --rm horcrux python -c "import horcrux.server"`
Expected: 빌드 성공

- [ ] **Step 4: README 배포 절 추가** — 내용: Railway 프로젝트 생성(GitHub 연동, 볼륨 `/data` 마운트), Supabase 프로젝트 생성 → `db/schema.sql` SQL 에디터 실행 → Auth에서 구글 provider 켜기 → legacy JWT secret 발급, Railway 환경변수 목록(Global Constraints의 8개), 중앙 모드 기본·연구실 크레덴셜 등록 절차(관리자 화면 또는 운영자 대행 — `claude setup-token` 안내).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "build: Dockerfile·배포 문서 — Railway+Supabase" && git push origin backend
```

---

### Task 9: 문서 정리 + 최종 검증

**Files:**
- Modify: `docs/superpowers/specs/2026-08-06-deployment-auth-design.md`(사용량 카운트 단위를 "LLM 유발 요청 1건 = 1"로 정정), `AGENTS.md`(봇 언급 제거·배포 모드 한 줄 추가)

- [ ] **Step 1: 스펙 정정** — "LLM 호출 1회마다 llm_usage upsert 증가"를 "LLM 유발 API 요청(parse/ask/records) 1건마다 증가"로. AGENTS.md에서 discord/bot 언급 제거.

- [ ] **Step 2: 전체 스위트 + 로컬 스모크**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=.pytest_tmp`
Expected: PASS
Run: `PYTHONPATH=src python -c "from horcrux.server import create_app; from horcrux.config import load_config; create_app(load_config())"`
Expected: 에러 없음 (로컬 모드 앱 생성)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "docs: 배포 스펙 정정·봇 잔재 제거" && git push origin backend
```

---

## 계획 외 (수동·타 세션)

- Supabase·Railway 프로젝트 생성과 env 입력: 운영자(사용자) 수동 — Task 8의 README 절차 따라.
- 프론트(로그인·온보딩·설정 화면): `docs/superpowers/specs/2026-08-06-frontend-tasks.md` — 프론트 세션.
- 실배포 E2E 스모크(가입→연구실 생성→기록→질의): 백엔드+프론트 머지 후 수동 1회.

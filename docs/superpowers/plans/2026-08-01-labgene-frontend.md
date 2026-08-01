# LAB GENE 프론트엔드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** horcrux 코어를 FastAPI로 감싸고 React SPA(LAB GENE)로 기록·진단·피드백 전 흐름을 브라우저에서 시연.

**Architecture:** `src/horcrux/server.py`(FastAPI, stateless thin wrapper) + `web/`(Vite+React+TS+Tailwind SPA). 대화 상태는 프론트 localStorage, LLM 호출은 동기 엔드포인트(스레드풀). `horcrux serve` 하나로 정적 빌드 서빙. 스펙: `docs/superpowers/specs/2026-08-01-labgene-frontend-design.md`.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn / React 18, TypeScript, Vite, Tailwind v4, react-router-dom(HashRouter), vitest.

## Global Constraints

- **검증 최소화 (사용자 요청)**: TDD 사이클 없음. 태스크당 검증 1회 — 백엔드 `python -m pytest -q --basetemp=.pytest_tmp`, 프론트 `npm run build`(타입체크 겸용) 또는 지정된 vitest 1회. 그 외 수동 확인 생략.
- 백엔드 코어 수정은 스펙이 허용한 2개뿐: `records.py` followup_of, `diagnose.py` 분해. 나머지는 신규 파일.
- 모든 파일 I/O `encoding="utf-8"` (Windows cp949 환경).
- UI 카피는 전부 한국어, 브랜드 표기 **LAB GENE**. 코드 식별자는 영어.
- 볼트 쓰기는 `server.py`의 `_VAULT_LOCK` 경유 (bot.py와 동일한 이유 — id 순번 경쟁 방지).
- 라우팅은 HashRouter(`/#/notes`) — 정적 서빙 SPA fallback 불필요.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- git push 금지 (사용자 지시).

---

### Task 1: 백엔드 — followup_of 필드 + diagnose 분해

**Files:**
- Modify: `src/horcrux/records.py` (ExperimentRecord에 필드 1개)
- Modify: `src/horcrux/diagnose.py` (diagnose_data 신설, diagnose는 래퍼로)
- Modify: `tests/test_records.py`, `tests/test_diagnose.py` (각 1~2개 추가)

**Interfaces:**
- Produces: `ExperimentRecord.followup_of: str | None`(frontmatter 라운드트립 포함),
  `diagnose_data(cfg, text) -> dict` — 반환 형태:
  `{"answer": str, "evidence": "records"|"wiki"|"none", "records": [{"id","date","experiment_type","objective","symptom":{...},"resolution":{...}}], "wiki": [str]}`
- 기존 `diagnose(cfg, text) -> str`의 CLI 출력(⚠/ℹ 프리픽스 포함)은 불변.

- [ ] **Step 1: records.py — 필드 추가**

`ExperimentRecord`에 한 줄 추가 (`needs_review` 위):

```python
    resolution: Resolution = Field(default_factory=Resolution)
    followup_of: str | None = None  # 후속 실험이면 기준 레코드 id
    needs_review: bool = False
```

- [ ] **Step 2: diagnose.py — diagnose_data 분리**

`diagnose` 함수를 다음 둘로 교체 (`run_ask`는 불변, import에 `load_record` 추가):

```python
from .records import load_record


def diagnose_data(cfg: Config, text: str) -> dict:
    res = retrieve(cfg, text)
    cases = "\n\n".join(
        f"### 사례 {r['id']}\n" + Path(r["path"]).read_text(encoding="utf-8")
        for r in res["records"]
    ) or "(축적된 유사 사례 없음)"
    wiki = "\n\n".join(
        f"### 위키/{w['id']}\n" + Path(w["path"]).read_text(encoding="utf-8")
        for w in res["wiki"]
    ) or "(없음)"
    user = f"## 질의\n{text}\n\n## 유사 사례\n{cases}\n\n## 위키 아티클\n{wiki}"
    answer = generate(cfg, ANSWER_SYSTEM, user)
    if not res["records"] and not res["wiki"]:
        evidence = "none"
    elif not res["records"]:
        evidence = "wiki"
    else:
        evidence = "records"
    records_meta = []
    for r in res["records"]:
        rec, _ = load_record(Path(r["path"]))
        records_meta.append({
            "id": rec.id, "date": rec.date, "experiment_type": rec.experiment_type,
            "objective": rec.objective, "symptom": rec.symptom.model_dump(),
            "resolution": rec.resolution.model_dump(),
        })
    return {"answer": answer, "evidence": evidence,
            "records": records_meta, "wiki": [w["id"] for w in res["wiki"]]}


def diagnose(cfg: Config, text: str) -> str:
    d = diagnose_data(cfg, text)
    answer = d["answer"]
    if d["evidence"] == "none":
        answer = "⚠ 아직 축적된 유사 사례가 없습니다. 아래는 일반 지식 기반 조언입니다.\n\n" + answer
    elif d["evidence"] == "wiki":
        answer = "ℹ 직접 유사한 실험 레코드는 없어, 아래는 연구실 위키 아티클 기반 조언입니다.\n\n" + answer
    return answer
```

- [ ] **Step 3: 테스트 추가**

`tests/test_records.py`에 — **기존 import 줄에 `record_path`를 먼저 추가**
(현재 import에 없어 그대로 붙이면 NameError):

```python
def test_followup_of_roundtrip(tmp_path):
    rec = ExperimentRecord(id="2026-08-01_x-001", date="2026-08-01",
                           followup_of="2026-07-31_x-001")
    save_record(tmp_path, rec, "원문", "요약")
    loaded, _ = load_record(record_path(tmp_path, rec.id))
    assert loaded.followup_of == "2026-07-31_x-001"
```

`tests/test_diagnose.py`에 (기존 모킹 패턴 따라 `diagnose` 모듈의 `retrieve`·`generate`를 monkeypatch — 기존 테스트 파일의 픽스처/헬퍼를 먼저 읽고 같은 방식 사용):

```python
def test_diagnose_data_shape(tmp_path, monkeypatch):
    from horcrux import diagnose as dg
    from horcrux.records import ExperimentRecord, save_record, record_path
    rec = ExperimentRecord(id="2026-08-01_exp-001", date="2026-08-01", experiment_type="증착")
    save_record(tmp_path, rec, "원문", "요약")
    monkeypatch.setattr(dg, "retrieve", lambda cfg, q: {
        "records": [{"id": rec.id, "path": str(record_path(tmp_path, rec.id))}], "wiki": []})
    monkeypatch.setattr(dg, "generate", lambda cfg, s, u: "답변")
    d = dg.diagnose_data(Config(vault=tmp_path), "질문")
    assert d["evidence"] == "records"
    assert d["records"][0]["id"] == rec.id
    assert d["answer"] == "답변"
```

- [ ] **Step 4: 검증 1회 + 커밋**

```bash
python -m pytest -q --basetemp=.pytest_tmp
git add -A && git commit -m "feat: followup_of 필드 + diagnose_data 분해 (웹 API 대비)"
```

---

### Task 2: server.py — FastAPI 엔드포인트 + serve 명령

**Files:**
- Create: `src/horcrux/server.py`
- Modify: `src/horcrux/cli.py` (serve 서브커맨드)
- Modify: `pyproject.toml` ([web] extra)
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: Task 1의 `diagnose_data`, `ExperimentRecord.followup_of`.
- Produces (프론트가 쓰는 API 계약 — Task 4 `api.ts`가 그대로 미러):
  - `POST /api/parse` `{text}` → `{parsed: ParsedLog, gaps: string[]}`
  - `POST /api/records` `{text, parsed: ParsedLog, followup_of?}` → `{id, path}` (absorb는 BackgroundTasks)
  - `POST /api/records/raw` `{text}` → `{id, path}`
  - `POST /api/ask` `{text}` → diagnose_data dict 그대로
  - `GET /api/records` → `{records: RecordMeta[]}` (id 내림차순)
  - `GET /api/records/{id}` → `{record: <frontmatter 전체>, body: string}` / 404
  - `POST /api/feedback` `{record_id, resolved, cause?, note?}` → `{message}` / 404
  - `GET /api/config` → `{required_fields, required_parameters, provider, vault}`
  - RecordMeta = ExperimentRecord.model_dump()에서 `id,date,experiment_type,objective,equipment,materials,symptom,resolution,needs_review,followup_of`

- [ ] **Step 1: server.py 작성**

```python
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

# ponytail: bot.py와 같은 전역 볼트 쓰기 락 — 저장 id 순번 경쟁 방지 (로컬 단일 사용자)
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
```

- [ ] **Step 2: cli.py — serve 서브커맨드**

`sub.add_parser("bot", ...)` 아래에 추가:

```python
    sv = sub.add_parser("serve", help="웹 UI 서버 (LAB GENE)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
```

분기(`elif args.cmd == "bot":` 아래):

```python
        elif args.cmd == "serve":
            from .server import run_serve
            run_serve(cfg, args.host, args.port)
```

- [ ] **Step 3: pyproject.toml — [web] extra**

```toml
[project.optional-dependencies]
dev = ["pytest"]
release = ["build", "pyinstaller"]
web = ["fastapi", "uvicorn"]
```

- [ ] **Step 4: tests/test_server.py 작성**

LLM 경유 함수(parse_log, diagnose_data, run_absorb)는 전부 monkeypatch — LLM 호출 없음.

```python
import pytest
from fastapi.testclient import TestClient

from horcrux import server
from horcrux.config import Config
from horcrux.ingest import ParsedLog
from horcrux.records import ExperimentRecord, record_path, save_record


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "run_absorb", lambda cfg: 0)
    return TestClient(server.create_app(Config(vault=tmp_path))), tmp_path


def test_parse_returns_parsed_and_gaps(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(server, "parse_log",
                        lambda cfg, text, vcfg: ParsedLog(objective="막 증착"))
    r = c.post("/api/parse", json={"text": "오늘 증착"})
    assert r.status_code == 200
    assert r.json()["parsed"]["objective"] == "막 증착"
    assert any("결과" in g for g in r.json()["gaps"])  # results 미기재 → 재질문


def test_save_creates_record_with_followup(client):
    c, vault = client
    parsed = ParsedLog(experiment_type="증착", objective="o", results="r",
                       summary="요약").model_dump()
    r = c.post("/api/records", json={"text": "원문", "parsed": parsed,
                                     "followup_of": "2026-07-31_x-001"})
    assert r.status_code == 200
    rid = r.json()["id"]
    assert record_path(vault, rid).exists()
    detail = c.get(f"/api/records/{rid}").json()
    assert detail["record"]["followup_of"] == "2026-07-31_x-001"
    assert "원문" in detail["body"]


def test_save_raw_needs_review(client):
    c, _ = client
    r = c.post("/api/records/raw", json={"text": "깨진 로그"})
    rid = r.json()["id"]
    detail = c.get(f"/api/records/{rid}").json()
    assert detail["record"]["needs_review"] is True


def test_ask_passthrough(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(server, "diagnose_data", lambda cfg, t: {
        "answer": "a", "evidence": "none", "records": [], "wiki": []})
    assert c.post("/api/ask", json={"text": "q"}).json()["evidence"] == "none"


def test_list_and_detail_404(client):
    c, vault = client
    save_record(vault, ExperimentRecord(id="2026-08-01_a-001", date="2026-08-01"), "원문", "s")
    assert c.get("/api/records").json()["records"][0]["id"] == "2026-08-01_a-001"
    assert c.get("/api/records/없는-id").status_code == 404


def test_feedback_updates_resolution(client):
    c, vault = client
    save_record(vault, ExperimentRecord(id="2026-08-01_b-001", date="2026-08-01"), "원문", "s")
    r = c.post("/api/feedback", json={"record_id": "2026-08-01_b-001",
                                      "resolved": True, "cause": "타겟 산화"})
    assert r.status_code == 200
    detail = c.get("/api/records/2026-08-01_b-001").json()
    assert detail["record"]["resolution"]["resolved"] is True
    assert detail["record"]["resolution"]["actual_cause"] == "타겟 산화"


def test_config_endpoint(client):
    c, _ = client
    j = c.get("/api/config").json()
    assert "objective" in j["required_fields"]
    assert j["provider"] == "claude"
```

- [ ] **Step 5: 검증 1회 + 커밋**

```bash
pip install -e ".[web,dev]" httpx
python -m pytest -q --basetemp=.pytest_tmp
git add -A && git commit -m "feat: FastAPI server + horcrux serve 명령"
```

(TestClient는 httpx 필요 — dev extra에 넣지 않고 설치만: 데모 배포엔 불필요.)

---

### Task 3: web/ 스캐폴드 — Vite + React + TS + Tailwind + 라우팅 셸

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`
- Create: `web/src/main.tsx`, `web/src/App.tsx`, `web/src/index.css`
- Create: `web/src/types.ts`, `web/src/api.ts`, `web/src/store.ts`
- Create: `web/src/components/Sidebar.tsx`
- Modify: `.gitignore` (`web/node_modules/`, `web/dist/`)

**Interfaces:**
- Produces (이후 모든 태스크가 사용):
  - `types.ts`: `ParsedLog`, `RecordMeta`, `RecordDetail`, `AskResult`, `AppConfig`, `ChatMsg`, `Session`
  - `api.ts`: `api.parse(text)`, `api.saveRecord(text, parsed, followupOf?)`, `api.saveRaw(text)`, `api.ask(text)`, `api.listRecords()`, `api.getRecord(id)`, `api.feedback(recordId, resolved, cause?, note?)`, `api.config()`
  - `store.ts`: `listSessions()`, `getSession(id)`, `saveSession(s)`, `deleteSession(id)`, `newSession(kind, baseId?)`
  - 라우트: `#/` 홈, `#/log/:sid` 기록, `#/ask/:sid` 질문, `#/preview/:sid` 미리보기, `#/notes` `#/notes/:id` 연구노트, `#/followup/:sid` 후속

- [ ] **Step 1: 스캐폴드 파일 작성**

`web/package.json`:

```json
{
  "name": "labgene-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@testing-library/react": "^16.1.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0"
  }
}
```

`web/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  test: { environment: "jsdom", globals: true },
});
```

`web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

`web/index.html`:

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LAB GENE</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`web/src/index.css`:

```css
@import "tailwindcss";
```

`web/src/types.ts` (백엔드 pydantic 모델 미러 — Task 2 계약과 1:1):

```ts
export interface Parameter { name: string; value: string; controllable: boolean }
export interface Symptom {
  category: "low_value" | "unstable" | "abnormal" | "none";
  description: string;
}
export interface SuspectedCause {
  cause: string;
  status: "unconfirmed" | "confirmed" | "rejected";
}
export interface Resolution { resolved: boolean; actual_cause: string | null; note: string }

export interface ParsedLog {
  experiment_type: string;
  objective: string;
  equipment: string[];
  materials: string[];
  parameters: Parameter[];
  results: string;
  symptom: Symptom;
  suspected_causes: SuspectedCause[];
  actions_taken: string[];
  summary: string;
  unrecorded_required_parameters: string[];
}

export interface RecordMeta {
  id: string; date: string; experiment_type: string; objective: string;
  equipment: string[]; materials: string[]; symptom: Symptom;
  resolution: Resolution; needs_review: boolean; followup_of: string | null;
}
export interface RecordDetail {
  record: RecordMeta & {
    parameters: Parameter[]; results: string;
    suspected_causes: SuspectedCause[]; actions_taken: string[];
  };
  body: string;
}
export interface AskResult {
  answer: string;
  evidence: "records" | "wiki" | "none";
  records: Pick<RecordMeta, "id" | "date" | "experiment_type" | "objective" | "symptom" | "resolution">[];
  wiki: string[];
}
export interface AppConfig {
  required_fields: string[]; required_parameters: string[];
  provider: string; vault: string;
}

export interface ChatMsg { role: "user" | "ai"; text: string; chips?: string[] }
export interface Session {
  id: string;
  kind: "log" | "ask" | "followup";
  title: string;
  createdAt: number;
  saved: boolean;          // 레코드로 저장 완료 여부 (log/followup)
  baseId?: string;         // followup: 기준 레코드 id
  rawText: string;         // 누적 원문
  messages: ChatMsg[];
  parsed: ParsedLog | null;
  gaps: string[];
  gapIndex: number;        // 현재 질문 중인 gap
  answers: string[];       // 로컬 누적 답변 (재파싱 전)
  rounds: number;          // 재파싱 횟수 (최대 3)
  askResult?: AskResult;
}
```

`web/src/api.ts`:

```ts
import type { AppConfig, AskResult, ParsedLog, RecordDetail, RecordMeta } from "./types";

async function http<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `요청 실패 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  parse: (text: string) =>
    http<{ parsed: ParsedLog; gaps: string[] }>("POST", "/api/parse", { text }),
  saveRecord: (text: string, parsed: ParsedLog, followupOf?: string) =>
    http<{ id: string; path: string }>("POST", "/api/records",
      { text, parsed, followup_of: followupOf ?? null }),
  saveRaw: (text: string) =>
    http<{ id: string; path: string }>("POST", "/api/records/raw", { text }),
  ask: (text: string) => http<AskResult>("POST", "/api/ask", { text }),
  listRecords: () => http<{ records: RecordMeta[] }>("GET", "/api/records"),
  getRecord: (id: string) => http<RecordDetail>("GET", `/api/records/${id}`),
  feedback: (recordId: string, resolved: boolean, cause?: string, note?: string) =>
    http<{ message: string }>("POST", "/api/feedback",
      { record_id: recordId, resolved, cause: cause ?? null, note: note ?? "" }),
  config: () => http<AppConfig>("GET", "/api/config"),
};
```

`web/src/store.ts` (localStorage 세션):

```ts
import type { Session } from "./types";

const KEY = "labgene.sessions.v1";

function readAll(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as Session[];
  } catch {
    return [];
  }
}
function writeAll(list: Session[]) {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function listSessions(): Session[] {
  return readAll().sort((a, b) => b.createdAt - a.createdAt);
}
export function getSession(id: string): Session | undefined {
  return readAll().find((s) => s.id === id);
}
export function saveSession(s: Session) {
  const list = readAll().filter((x) => x.id !== s.id);
  list.push(s);
  writeAll(list);
}
export function deleteSession(id: string) {
  writeAll(readAll().filter((s) => s.id !== id));
}
export function newSession(kind: Session["kind"], baseId?: string): Session {
  const s: Session = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    kind, title: "새 대화", createdAt: Date.now(), saved: false, baseId,
    rawText: "", messages: [], parsed: null, gaps: [], gapIndex: 0,
    answers: [], rounds: 0,
  };
  saveSession(s);
  return s;
}
```

`web/src/components/Sidebar.tsx`:

```tsx
import { Link, useLocation, useNavigate } from "react-router-dom";
import { listSessions } from "../store";
import type { Session } from "../types";

function sessionPath(s: Session): string {
  if (s.kind === "ask") return `/ask/${s.id}`;
  if (s.kind === "followup") return `/followup/${s.id}`;
  return `/log/${s.id}`;
}

export default function Sidebar() {
  const nav = useNavigate();
  const loc = useLocation();
  const sessions = listSessions();
  const today = new Date().toDateString();
  const isToday = (s: Session) => new Date(s.createdAt).toDateString() === today;
  const group = (list: Session[], label: string) =>
    list.length > 0 && (
      <div className="mt-4">
        <div className="px-3 text-xs text-slate-400">{label}</div>
        {list.map((s) => (
          <Link key={s.id} to={sessionPath(s)}
            className={`block truncate rounded px-3 py-2 text-sm hover:bg-slate-100 ${
              loc.pathname.includes(s.id) ? "bg-blue-50 text-blue-700" : "text-slate-700"}`}>
            {s.title}
          </Link>
        ))}
      </div>
    );

  return (
    <div className="flex h-screen">
      <nav className="flex w-52 shrink-0 flex-col bg-slate-900 p-4 text-slate-200">
        <div className="mb-8 flex items-center gap-2 font-bold tracking-wide">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600">⚗</span>
          LAB GENE
        </div>
        <Link to="/" className={`rounded px-3 py-2 text-sm ${loc.pathname === "/" ? "bg-slate-700" : "hover:bg-slate-800"}`}>
          ✦ AI 워크스페이스
        </Link>
        <Link to="/notes" className={`mt-1 rounded px-3 py-2 text-sm ${loc.pathname.startsWith("/notes") ? "bg-slate-700" : "hover:bg-slate-800"}`}>
          ▤ 연구노트
        </Link>
      </nav>
      <aside className="w-60 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-3">
        <button onClick={() => nav("/")}
          className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700">
          + 새 대화
        </button>
        {group(sessions.filter(isToday), "오늘")}
        {group(sessions.filter((s) => !isToday(s)), "이전")}
      </aside>
    </div>
  );
}
```

`web/src/App.tsx` (페이지 컴포넌트는 이후 태스크에서 생성 — 이 태스크에서는 자리만 있는 빈 홈으로 빌드 통과):

```tsx
import { HashRouter, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";

function Placeholder({ name }: { name: string }) {
  return <div className="p-8 text-slate-500">{name}</div>;
}

export default function App() {
  return (
    <HashRouter>
      <div className="flex h-screen bg-slate-50 text-slate-900">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Placeholder name="홈" />} />
            <Route path="/log/:sid" element={<Placeholder name="기록" />} />
            <Route path="/ask/:sid" element={<Placeholder name="질문" />} />
            <Route path="/preview/:sid" element={<Placeholder name="미리보기" />} />
            <Route path="/notes" element={<Placeholder name="연구노트" />} />
            <Route path="/notes/:id" element={<Placeholder name="연구노트" />} />
            <Route path="/followup/:sid" element={<Placeholder name="후속 실험" />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
```

`web/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`.gitignore`에 추가:

```
web/node_modules/
web/dist/
```

- [ ] **Step 2: 검증 1회 + 커밋**

```bash
cd web && npm install && npm run build
cd .. && git add -A && git commit -m "feat: web 스캐폴드 — Vite+React+TS+Tailwind, api/store/사이드바 셸"
```

주의: App.tsx의 Placeholder 라우트는 Task 4~9가 실제 페이지로 순차 교체한다.

---

### Task 4: ① 홈 — 입력창 + 기록/질문 토글

**Files:**
- Create: `web/src/pages/Home.tsx`
- Modify: `web/src/App.tsx` (홈 라우트 교체)

**Interfaces:**
- Consumes: `newSession`, `saveSession`, `listSessions` (store), 라우트 `#/log/:sid`, `#/ask/:sid`
- Produces: 세션 생성 시 `session.rawText`에 첫 입력을 담아 저장 → LogChat/Ask 페이지가 마운트 시 `rawText`가 있고 `messages`가 비었으면 자동 시작 (Task 5·7이 이 규약을 따름)

- [ ] **Step 1: Home.tsx 작성**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions, newSession, saveSession } from "../store";

export default function Home() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"log" | "ask">("log");
  const [text, setText] = useState("");
  const drafts = listSessions().filter((s) => s.kind !== "ask" && !s.saved && s.messages.length > 0);

  function start(kind: "log" | "ask", preset?: string) {
    const t = (preset ?? text).trim();
    if (!t) return;
    const s = newSession(kind);
    s.rawText = t;
    s.title = t.slice(0, 30);
    saveSession(s);
    nav(kind === "log" ? `/log/${s.id}` : `/ask/${s.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="text-3xl font-bold">무엇을 도와드릴까요?</h1>
      <p className="mt-2 text-slate-500">실험 기록, 문제 원인, 과거 사례를 자연어로 입력하면 AI가 정리합니다.</p>

      <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm w-fit">
          {(["log", "ask"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`rounded-md px-4 py-1.5 ${mode === m ? "bg-white font-medium shadow" : "text-slate-500"}`}>
              {m === "log" ? "실험 기록" : "문제 질문"}
            </button>
          ))}
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
          placeholder={mode === "log" ? "실험 내용을 자유롭게 입력하세요." : "문제 상황을 설명해주세요. 장비·재료·증상을 포함하면 더 정확합니다."}
          className="w-full resize-none outline-none placeholder:text-slate-400" />
        <div className="flex justify-end">
          <button onClick={() => start(mode)} disabled={!text.trim()}
            className="rounded-full bg-blue-600 px-5 py-2 text-sm text-white disabled:opacity-40">
            전송 ➤
          </button>
        </div>
      </div>

      <div className="mt-10">
        <h2 className="mb-3 font-semibold">빠른 시작</h2>
        <div className="grid grid-cols-2 gap-4">
          <button onClick={() => setMode("log")}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm hover:border-blue-400 ${mode === "log" ? "border-blue-400" : "border-slate-200"}`}>
            <div className="font-medium">📄 오늘 실험을 기록할게요</div>
            <div className="mt-1 text-sm text-slate-500">실험 조건과 결과를 구조화합니다.</div>
          </button>
          <button onClick={() => setMode("ask")}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm hover:border-blue-400 ${mode === "ask" ? "border-blue-400" : "border-slate-200"}`}>
            <div className="font-medium">🔍 과거 유사 사례를 찾아주세요</div>
            <div className="mt-1 text-sm text-slate-500">연구실 기록에서 근거를 검색합니다.</div>
          </button>
        </div>
      </div>

      {drafts.length > 0 && (
        <div className="mt-10 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="font-medium">최근 미완료 기록 {drafts.length}건</div>
          <div className="text-sm text-slate-500">누락 정보를 이어서 입력하고 저장할 수 있어요.</div>
          <div className="mt-3 space-y-2">
            {drafts.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{d.title}</div>
                  <div className="text-xs text-slate-400">
                    {new Date(d.createdAt).toLocaleString("ko-KR")}
                    {d.kind === "followup" && " · 후속 실험"}
                  </div>
                </div>
                <button onClick={() => nav(d.kind === "followup" ? `/followup/${d.id}` : `/log/${d.id}`)}
                  className="shrink-0 rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
                  이어 작성
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: App.tsx 라우트 교체**

```tsx
import Home from "./pages/Home";
// Routes 안:
<Route path="/" element={<Home />} />
```

- [ ] **Step 3: 검증 1회 + 커밋**

```bash
cd web && npm run build
cd .. && git add -A && git commit -m "feat: 홈 — 입력창·기록/질문 토글·미완료 이어작성"
```

---

### Task 5: ② 연구 기록 chat — 하이브리드 재질문 루프 + 실시간 구조화 패널

**Files:**
- Create: `web/src/components/ChatPane.tsx`
- Create: `web/src/components/StructurePanel.tsx`
- Create: `web/src/pages/LogChat.tsx`
- Create: `web/src/components/StructurePanel.test.tsx`
- Modify: `web/src/App.tsx` (`/log/:sid`, `/followup/:sid` 라우트 교체 — LogChat 재사용)

**Interfaces:**
- Consumes: `api.parse`, `api.saveRaw`, store, Session 규약(Task 3), Home 규약(Task 4)
- Produces:
  - `<ChatPane messages onSend busy chips onChip>` — 말풍선 목록 + 입력창 + 퀵답변 칩 (Task 7 Ask도 재사용)
  - `<StructurePanel parsed gaps requiredTotal canSave onSaveClick saveLabel>` — 우측 패널.
    완성도 = `(requiredTotal - gaps.length) / requiredTotal` (gaps는 **마지막 파싱 기준 전체**
    — 답변 진행만으로 게이지가 차오르지 않게 하여 정직성 유지).
    `canSave` = 질문 루프 소진(`gapIndex >= gaps.length`) 또는 재질문 라운드 소진(`rounds >= 3`)
  - LogChat은 `session.kind === "followup"`이면 기준 레코드 패널·diff를 Task 9의 컴포넌트로 렌더 (Task 9에서 주입 — 이 태스크에서는 kind==="log"만 완성)
  - 저장 진입: gaps 소진 시 `#/preview/:sid`로 이동

- [ ] **Step 1: ChatPane.tsx**

```tsx
import { useEffect, useRef, useState } from "react";
import type { ChatMsg } from "../types";

export default function ChatPane({ messages, onSend, busy, placeholder }: {
  messages: ChatMsg[];
  onSend: (text: string) => void;
  busy: boolean;
  placeholder?: string;
}) {
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy]);

  function send(t: string) {
    if (!t.trim() || busy) return;
    setText("");
    onSend(t.trim());
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.map((m, i) => (
          <div key={i}>
            <div className={`text-xs text-slate-400 ${m.role === "user" ? "text-right" : ""}`}>
              {m.role === "user" ? "사용자" : "LAB GENE AI"}
            </div>
            <div className={m.role === "user"
              ? "ml-auto w-fit max-w-[80%] rounded-xl bg-blue-50 px-4 py-3 text-sm whitespace-pre-wrap"
              : "w-fit max-w-[85%] rounded-xl border-l-4 border-blue-500 bg-white px-4 py-3 text-sm shadow-sm whitespace-pre-wrap"}>
              {m.text}
            </div>
            {m.role === "ai" && m.chips && i === messages.length - 1 && !busy && (
              <div className="mt-2 flex flex-wrap gap-2">
                {m.chips.map((c) => (
                  <button key={c} onClick={() => send(c)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1 text-sm hover:border-blue-400 hover:text-blue-600">
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="text-sm text-slate-400 animate-pulse">분석 중... (수십 초 걸릴 수 있어요)</div>}
        <div ref={bottom} />
      </div>
      <div className="border-t border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2">
          <input value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(text)}
            placeholder={placeholder ?? "메시지를 입력하세요"} disabled={busy}
            className="flex-1 text-sm outline-none disabled:bg-transparent" />
          <button onClick={() => send(text)} disabled={busy || !text.trim()}
            className="rounded-full bg-blue-600 px-4 py-1.5 text-sm text-white disabled:opacity-40">➤</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: StructurePanel.tsx**

```tsx
import type { ParsedLog } from "../types";

function Row({ label, value }: { label: string; value: string }) {
  return value ? (
    <div className="mt-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-sm font-medium whitespace-pre-wrap">{value}</div>
    </div>
  ) : null;
}

export default function StructurePanel({ parsed, gaps, requiredTotal, canSave, onSaveClick, saveLabel }: {
  parsed: ParsedLog | null;
  gaps: string[];          // 마지막 파싱 기준 누락 항목 전체 (게이지 분자 계산)
  requiredTotal: number;
  canSave: boolean;        // 질문 루프 소진 또는 재질문 라운드 소진
  onSaveClick: () => void;
  saveLabel: string;
}) {
  const done = Math.max(requiredTotal - gaps.length, 0);
  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-l border-slate-200 bg-white p-5">
      <div className="text-lg font-bold">연구 기록</div>
      <div className="text-xs text-slate-400">실시간으로 구조화됩니다.</div>
      <div className="flex-1 overflow-y-auto">
        {!parsed && <div className="mt-8 text-sm text-slate-400">첫 메시지를 보내면 구조화가 시작됩니다.</div>}
        {parsed && (
          <>
            <Row label="실험 목적" value={parsed.objective} />
            <Row label="실험 유형" value={parsed.experiment_type} />
            <Row label="장비" value={parsed.equipment.join(", ")} />
            <Row label="재료" value={parsed.materials.join(", ")} />
            <Row label="조건" value={parsed.parameters.map((p) => `${p.name} ${p.value}`).join(" · ")} />
            <Row label="결과" value={parsed.results} />
            <Row label="증상" value={parsed.symptom.category === "none" ? "문제 없음" : parsed.symptom.description} />
            <Row label="조치" value={parsed.actions_taken.join(", ")} />
            {gaps.length > 0 && (
              <div className="mt-4">
                <div className="text-xs text-slate-400">누락 정보</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {gaps.map((g) => (
                    <span key={g} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                      {g.slice(0, 20)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">정보 완성도</span>
                <span data-testid="gauge-text" className="font-medium text-blue-600">{done} / {requiredTotal}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-blue-600"
                  style={{ width: `${requiredTotal ? (done / requiredTotal) * 100 : 0}%` }} />
              </div>
            </div>
          </>
        )}
      </div>
      <button onClick={onSaveClick} disabled={!parsed || !canSave}
        className="mt-4 rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white disabled:opacity-40">
        {saveLabel}
      </button>
      {parsed && !canSave && (
        <div className="mt-1 text-center text-xs text-slate-400">남은 질문에 답하면 저장할 수 있어요</div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: LogChat.tsx — 하이브리드 루프**

루프 규칙 (그릴 Q2 확정안):
1. 첫 메시지 → `api.parse` → gaps 있으면 질문 **하나씩** AI 말풍선(+칩: 항상 "건너뛰기", symptom 질문엔 "문제 없음" 추가).
2. 답변은 로컬 누적만(`answers`), 재파싱 없이 다음 gap 질문.
3. 마지막 gap까지 답하면: 답변이 하나라도 있으면 `rawText += "\n\n[추가 답변]\n..."` 후 `api.parse` 1회(rounds++), 전부 건너뛰었으면 재파싱 생략.
4. 재파싱 후에도 gaps 남고 rounds < 3이면 다시 1번부터, 아니면 저장 가능 상태.
5. requiredTotal = `config.required_fields.length + config.required_parameters.length`.

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import StructurePanel from "../components/StructurePanel";
import { getSession, saveSession } from "../store";
import type { Session } from "../types";

const MAX_ROUNDS = 3;

function chipsFor(gap: string): string[] {
  const chips = ["건너뛰기"];
  if (gap.includes("증상")) chips.unshift("문제 없음");
  return chips;
}

export default function LogChat() {
  const { sid } = useParams();
  const nav = useNavigate();
  const [session, setSession] = useState<Session | null>(() => getSession(sid ?? "") ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requiredTotal, setRequiredTotal] = useState(5);
  const started = useRef(false);

  useEffect(() => {
    api.config().then((c) =>
      setRequiredTotal(c.required_fields.length + c.required_parameters.length));
  }, []);

  function update(s: Session) {
    saveSession(s);
    setSession({ ...s });
  }

  async function runParse(s: Session) {
    setBusy(true);
    setError(null);
    try {
      const { parsed, gaps } = await api.parse(s.rawText);
      s.parsed = parsed;
      s.gaps = gaps;
      s.gapIndex = 0;
      s.answers = [];
      if (parsed.experiment_type || parsed.objective)
        s.title = parsed.experiment_type || parsed.objective.slice(0, 30);
      if (gaps.length > 0 && s.rounds < MAX_ROUNDS) {
        s.messages.push({ role: "ai", text: gaps[0], chips: chipsFor(gaps[0]) });
      } else if (gaps.length === 0) {
        s.messages.push({ role: "ai", text: "필요한 정보가 모두 채워졌습니다. 우측에서 검토 후 저장하세요." });
      } else {
        s.messages.push({ role: "ai", text: `아직 ${gaps.length}개 항목이 비어 있지만 재질문을 마칩니다. 우측에서 검토 후 저장하세요.` });
      }
      update(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // 홈에서 rawText만 담겨 넘어온 세션 자동 시작 (Task 4 규약)
  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    if (session.rawText && session.messages.length === 0) {
      session.messages.push({ role: "user", text: session.rawText });
      void runParse(session);
    }
  }, [session]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  async function onSend(text: string) {
    const s = session!;
    s.messages.push({ role: "user", text });
    if (!s.parsed) {
      // 첫 파싱 실패 후 재시도 케이스: 원문에 이어붙여 재파싱
      s.rawText = s.rawText ? `${s.rawText}\n${text}` : text;
      update(s);
      await runParse(s);
      return;
    }
    // gap 답변 수집 (재파싱 없음)
    if (text !== "건너뛰기") s.answers.push(text);
    s.gapIndex += 1;
    if (s.gapIndex < s.gaps.length) {
      const g = s.gaps[s.gapIndex];
      s.messages.push({ role: "ai", text: g, chips: chipsFor(g) });
      update(s);
      return;
    }
    // 마지막 gap 소진 → 필요 시 재파싱 1회
    if (s.answers.length === 0) {
      // gaps는 지우지 않는다 — 게이지는 마지막 파싱 결과를 정직하게 유지, 저장은 canSave가 허용
      s.messages.push({ role: "ai", text: "확인했습니다. 누락된 항목은 비운 채로 저장됩니다. 우측에서 검토하세요." });
      update(s);
      return;
    }
    s.rawText += `\n\n[추가 답변]\n${s.answers.join("\n")}`;
    s.rounds += 1;
    update(s);
    await runParse(s);
  }

  async function onSaveRaw() {
    const s = session!;
    const { id } = await api.saveRaw(s.rawText);
    s.saved = true;
    update(s);
    nav(`/notes/${id}`);
  }

  // 질문 루프를 끝냈거나 재질문 라운드를 소진해야 저장 진입 (스펙 ②)
  const canSave = session.gapIndex >= session.gaps.length || session.rounds >= MAX_ROUNDS;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">연구 기록</div>
        </header>
        {error && (
          <div className="flex items-center gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장 (needs_review)</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} onSend={onSend} busy={busy} />
        </div>
      </div>
      <StructurePanel parsed={session.parsed} gaps={session.gaps} canSave={canSave}
        requiredTotal={requiredTotal} saveLabel="검토 후 저장"
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}
```

- [ ] **Step 4: App.tsx 라우트 교체**

```tsx
import LogChat from "./pages/LogChat";
// Routes 안 (/followup/:sid는 Task 9에서 전용 페이지로 재교체):
<Route path="/log/:sid" element={<LogChat />} />
```

- [ ] **Step 5: 최소 테스트 2개 (스펙 지정: ② 게이지·칩 흐름)**

`web/src/components/StructurePanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import StructurePanel from "./StructurePanel";
import type { ParsedLog } from "../types";

const parsed: ParsedLog = {
  experiment_type: "증착", objective: "막 50nm", equipment: ["ALD-02"], materials: [],
  parameters: [{ name: "온도", value: "250C", controllable: true }], results: "",
  symptom: { category: "none", description: "" }, suspected_causes: [],
  actions_taken: [], summary: "", unrecorded_required_parameters: [],
};

test("게이지가 (전체-누락)/전체 를 표시한다", () => {
  render(<StructurePanel parsed={parsed} gaps={["결과?", "조치?"]} requiredTotal={5}
    canSave={false} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  expect(screen.getByTestId("gauge-text").textContent).toBe("3 / 5");
});

test("질문 루프가 안 끝나면 저장 버튼 비활성", () => {
  render(<StructurePanel parsed={parsed} gaps={["결과?"]} requiredTotal={5}
    canSave={false} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  expect((screen.getByRole("button", { name: "검토 후 저장" }) as HTMLButtonElement).disabled)
    .toBe(true);
});

test("파싱 전에는 저장 버튼 비활성", () => {
  render(<StructurePanel parsed={null} gaps={[]} requiredTotal={5}
    canSave={true} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  // jest-dom 매처(toBeDisabled)는 의존성 추가가 필요하므로 내장 매처만 사용
  expect((screen.getByRole("button", { name: "검토 후 저장" }) as HTMLButtonElement).disabled)
    .toBe(true);
});
```

`web/src/components/ChatPane.test.tsx` (스펙 지정 최소 테스트 — ② 칩 흐름):

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import ChatPane from "./ChatPane";
import type { ChatMsg } from "../types";

const msgs: ChatMsg[] = [
  { role: "user", text: "오늘 증착했어" },
  { role: "ai", text: "문제나 이상 증상이 있었나요?", chips: ["문제 없음", "건너뛰기"] },
];

test("마지막 AI 메시지의 칩을 누르면 그 텍스트로 전송된다", () => {
  const sent: string[] = [];
  render(<ChatPane messages={msgs} onSend={(t) => sent.push(t)} busy={false} />);
  fireEvent.click(screen.getByRole("button", { name: "건너뛰기" }));
  expect(sent).toEqual(["건너뛰기"]);
});

test("처리 중(busy)에는 칩이 표시되지 않는다", () => {
  render(<ChatPane messages={msgs} onSend={() => {}} busy={true} />);
  expect(screen.queryByRole("button", { name: "건너뛰기" })).toBeNull();
});
```

- [ ] **Step 6: 검증 1회 + 커밋**

```bash
cd web && npx vitest run src/components && npm run build
cd .. && git add -A && git commit -m "feat: 기록 chat — 하이브리드 재질문 루프·실시간 구조화 패널"
```

---

### Task 6: ④ 저장 전 미리보기 — 편집 폼 + 저장

**Files:**
- Create: `web/src/pages/Preview.tsx`
- Modify: `web/src/App.tsx` (`/preview/:sid` 교체)

**Interfaces:**
- Consumes: `api.saveRecord`, `api.getRecord`(followup 기준 조회), `api.feedback`, store
- Produces: 저장 성공 → 세션 `saved=true` → `#/notes/:id` 이동. followup 세션(baseId 있음)이면 기준 레코드 미해결 시 "기준 실험 원인 상태 업데이트" 옵션 표시(그릴 확정: 결정론 — LLM 판단 없음), 선택 시 저장 후 `api.feedback(baseId, true, cause)` 순차 호출.

- [ ] **Step 1: Preview.tsx 작성**

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { getSession, saveSession } from "../store";
import type { ParsedLog, RecordDetail } from "../types";

function Field({ label, value, onChange, rows = 1 }: {
  label: string; value: string; onChange: (v: string) => void; rows?: number;
}) {
  return (
    <label className="block">
      <div className="text-xs text-slate-400">{label}</div>
      <textarea value={value} rows={rows} onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full resize-none rounded border border-slate-200 px-2 py-1.5 text-sm font-medium" />
    </label>
  );
}

export default function Preview() {
  const { sid } = useParams();
  const nav = useNavigate();
  const session = getSession(sid ?? "");
  const [p, setP] = useState<ParsedLog | null>(session?.parsed ?? null);
  const [base, setBase] = useState<RecordDetail | null>(null);
  const [updateBase, setUpdateBase] = useState(false);
  const [baseCause, setBaseCause] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);  // 저장 성공 후 재시도 시 중복 생성 방지

  useEffect(() => {
    if (session?.baseId) api.getRecord(session.baseId).then(setBase).catch(() => {});
  }, [session?.baseId]);

  if (!session || !p) return <div className="p-8 text-slate-500">미리볼 파싱 결과가 없습니다.</div>;
  if (session.saved && !savedId)
    return (
      <div className="p-8 text-slate-500">
        이미 저장된 대화입니다.{" "}
        <button onClick={() => nav("/notes")} className="text-blue-600 underline">연구노트에서 보기</button>
      </div>
    );
  const set = (patch: Partial<ParsedLog>) => setP({ ...p, ...patch });
  const showBaseUpdate = base && !base.record.resolution.resolved;

  async function onSave() {
    setBusy(true);
    setError(null);
    try {
      // 레코드는 한 번만 생성 — feedback 실패 후 재시도해도 중복 레코드가 생기지 않게 id 보관
      let id = savedId;
      if (!id) {
        id = (await api.saveRecord(session!.rawText, p!, session!.baseId)).id;
        setSavedId(id);
        session!.saved = true;
        saveSession(session!);
      }
      if (updateBase && session!.baseId && baseCause.trim())
        await api.feedback(session!.baseId, true, baseCause.trim());
      nav(`/notes/${id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="text-2xl font-bold">저장 전 기록 미리보기</h1>
      <p className="text-sm text-slate-500">AI가 정리한 내용을 확인하고 수정하세요.</p>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="font-semibold">기본 정보</div>
          <Field label="실험 유형" value={p.experiment_type} onChange={(v) => set({ experiment_type: v })} />
          <Field label="실험 목적" value={p.objective} onChange={(v) => set({ objective: v })} />
          <Field label="장비 (쉼표 구분)" value={p.equipment.join(", ")}
            onChange={(v) => set({ equipment: v.split(",").map((x) => x.trim()).filter(Boolean) })} />
          <Field label="재료 (쉼표 구분)" value={p.materials.join(", ")}
            onChange={(v) => set({ materials: v.split(",").map((x) => x.trim()).filter(Boolean) })} />
        </div>
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="font-semibold">조건·결과</div>
          <Field label="공정변수 (이름=값, 쉼표 구분)"
            value={p.parameters.map((x) => `${x.name}=${x.value}`).join(", ")}
            onChange={(v) => set({
              parameters: v.split(",").map((x) => x.trim()).filter((x) => x.includes("=")).map((x) => {
                const [name, ...rest] = x.split("=");
                return { name: name.trim(), value: rest.join("=").trim(), controllable: true };
              }),
            })} />
          <Field label="결과" value={p.results} rows={2} onChange={(v) => set({ results: v })} />
          <label className="block">
            <div className="text-xs text-slate-400">증상 분류</div>
            <select value={p.symptom.category}
              onChange={(e) => set({ symptom: { ...p.symptom, category: e.target.value as ParsedLog["symptom"]["category"] } })}
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm font-medium">
              <option value="none">문제 없음</option>
              <option value="low_value">값이 낮음</option>
              <option value="unstable">불안정·재현성</option>
              <option value="abnormal">비정상 거동</option>
            </select>
          </label>
          <Field label="증상 설명" value={p.symptom.description} rows={2}
            onChange={(v) => set({ symptom: { ...p.symptom, description: v } })} />
          <Field label="조치 (쉼표 구분)" value={p.actions_taken.join(", ")}
            onChange={(v) => set({ actions_taken: v.split(",").map((x) => x.trim()).filter(Boolean) })} />
          <Field label="원인 후보 (쉼표 구분 — 피드백 시 확정 원인 선택지가 됨)"
            value={p.suspected_causes.map((c) => c.cause).join(", ")}
            onChange={(v) => set({
              suspected_causes: v.split(",").map((x) => x.trim()).filter(Boolean)
                .map((cause) => ({ cause, status: "unconfirmed" as const })),
            })} />
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="font-semibold">정리 요약</div>
        <Field label="요약" value={p.summary} rows={3} onChange={(v) => set({ summary: v })} />
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-slate-500">원문 로그 (읽기 전용)</summary>
          <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{session.rawText}</pre>
        </details>
      </div>

      {showBaseUpdate && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <label className="flex items-center gap-2 font-medium">
            <input type="checkbox" checked={updateBase} onChange={(e) => setUpdateBase(e.target.checked)} />
            기준 실험({base!.record.id})의 원인 상태 업데이트 — 미확정 ➔ 확인됨
          </label>
          {updateBase && (
            <div className="mt-3 flex flex-wrap gap-2">
              {base!.record.suspected_causes.map((c) => (
                <button key={c.cause} onClick={() => setBaseCause(c.cause)}
                  className={`rounded-full border px-3 py-1 text-sm ${baseCause === c.cause ? "border-emerald-600 bg-white font-medium" : "border-slate-300 bg-white"}`}>
                  {c.cause}
                </button>
              ))}
              <input value={baseCause} onChange={(e) => setBaseCause(e.target.value)}
                placeholder="확정 원인 직접 입력" className="rounded border border-slate-300 px-2 py-1 text-sm" />
            </div>
          )}
        </div>
      )}

      <div className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-blue-800">
        ⑂ 저장하면 자동으로 생성됩니다 — 위키 아티클(백그라운드 편찬)
      </div>

      {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
      <div className="mt-6 flex justify-end gap-3">
        <button onClick={() => nav(-1)} className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm">
          수정하기 (대화로 돌아가기)
        </button>
        <button onClick={onSave} disabled={busy}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "저장 중..." : "저장하기"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: App.tsx 라우트 교체 + 검증 1회 + 커밋**

```tsx
import Preview from "./pages/Preview";
<Route path="/preview/:sid" element={<Preview />} />
```

```bash
cd web && npm run build
cd .. && git add -A && git commit -m "feat: 저장 전 미리보기 — 편집 폼·기준 원인 업데이트 옵션·저장"
```

---

### Task 7: ③ 과거 기록 분석 (ask)

**Files:**
- Create: `web/src/components/RecordCard.tsx`
- Create: `web/src/pages/Ask.tsx`
- Modify: `web/src/App.tsx` (`/ask/:sid` 교체)

**Interfaces:**
- Consumes: `api.ask`, ChatPane, store, Home 규약(rawText 자동 시작)
- Produces: `<RecordCard meta onClick>` — id·유형·해결 라벨 카드 (Task 8 목록에서도 재사용).
  해결 라벨 규칙(스펙): `symptom.category === "none"` → "문제 없음"(회색) / `resolution.resolved` → "원인 확인됨"(초록, actual_cause 병기) / 그 외 → "미해결"(주황)

- [ ] **Step 1: RecordCard.tsx**

```tsx
import type { RecordMeta } from "../types";

type CardMeta = Pick<RecordMeta, "id" | "experiment_type" | "objective" | "symptom" | "resolution">;

export function resolutionLabel(m: CardMeta): { text: string; cls: string } {
  if (m.symptom.category === "none") return { text: "문제 없음", cls: "bg-slate-100 text-slate-600" };
  if (m.resolution.resolved)
    return { text: `원인 확인됨${m.resolution.actual_cause ? " · " + m.resolution.actual_cause : ""}`,
             cls: "bg-emerald-100 text-emerald-700" };
  return { text: "미해결", cls: "bg-amber-100 text-amber-700" };
}

export default function RecordCard({ meta, onClick }: { meta: CardMeta; onClick: () => void }) {
  const label = resolutionLabel(meta);
  return (
    <button onClick={onClick}
      className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-blue-400">
      <div className="text-xs font-medium text-blue-600">{meta.id}</div>
      <div className="mt-1 font-medium">{meta.objective || meta.experiment_type || "(제목 없음)"}</div>
      <span className={`mt-2 inline-block rounded-full px-2 py-0.5 text-xs ${label.cls}`}>{label.text}</span>
    </button>
  );
}
```

- [ ] **Step 2: Ask.tsx**

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import RecordCard from "../components/RecordCard";
import { getSession, saveSession } from "../store";
import type { Session } from "../types";

// 근거 3단 라벨 (스펙 ③) — records 단도 표시해야 3단이 성립
const BANNERS = {
  none: { text: "⚠ 축적된 유사 사례가 없어 일반 지식 기반 조언입니다.", cls: "bg-red-50 text-red-700" },
  wiki: { text: "ℹ 유사 레코드는 없어 연구실 위키 아티클 기반 안내입니다.", cls: "bg-blue-50 text-blue-700" },
  records: { text: "✓ 연구실 실험 기록을 근거로 한 답변입니다.", cls: "bg-emerald-50 text-emerald-700" },
} as const;

export default function Ask() {
  const { sid } = useParams();
  const nav = useNavigate();
  const [session, setSession] = useState<Session | null>(() => getSession(sid ?? "") ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  function update(s: Session) {
    saveSession(s);
    setSession({ ...s });
  }

  async function runAsk(s: Session, text: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.ask(text);
      s.askResult = result;
      s.title = text.slice(0, 30);
      s.messages.push({ role: "ai", text: result.answer });
      update(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    if (session.rawText && session.messages.length === 0) {
      session.messages.push({ role: "user", text: session.rawText });
      void runAsk(session, session.rawText);
    }
  }, [session]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;
  const banner = session.askResult ? BANNERS[session.askResult.evidence] : null;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title === "새 대화" ? "과거 기록 분석" : session.title}</div>
          <div className="text-xs text-slate-400">과거 기록 분석</div>
        </header>
        {banner && <div className={`px-6 py-2 text-sm ${banner.cls}`}>{banner.text}</div>}
        {error && (
          <div className="flex gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runAsk(session, session.rawText)} className="underline">재시도</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} busy={busy}
            placeholder="추가 질문을 입력하세요"
            onSend={(t) => {
              session.messages.push({ role: "user", text: t });
              session.rawText = t;
              update(session);
              void runAsk(session, t);
            }} />
        </div>
      </div>
      <div className="w-80 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-5">
        <div className="text-lg font-bold">유사 사례</div>
        {!session.askResult && <div className="mt-4 text-sm text-slate-400">질문하면 관련 기록이 표시됩니다.</div>}
        <div className="mt-3 space-y-3">
          {session.askResult?.records.map((r) => (
            <RecordCard key={r.id} meta={r} onClick={() => nav(`/notes/${r.id}`)} />
          ))}
          {session.askResult && session.askResult.records.length === 0 && (
            <div className="text-sm text-slate-400">관련 레코드 없음</div>
          )}
        </div>
        {session.askResult && session.askResult.wiki.length > 0 && (
          <div className="mt-5">
            <div className="text-xs text-slate-400">참고한 위키</div>
            {session.askResult.wiki.map((w) => (
              <div key={w} className="mt-1 rounded bg-slate-50 px-2 py-1 text-sm">{w}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: App.tsx 라우트 교체 + 검증 1회 + 커밋**

```tsx
import Ask from "./pages/Ask";
<Route path="/ask/:sid" element={<Ask />} />
```

```bash
cd web && npm run build
cd .. && git add -A && git commit -m "feat: 과거 기록 분석 — 답변·유사 사례 카드·근거 3단 배너"
```

---

### Task 8: ⑤ 연구노트 + 실험 피드백 모달

**Files:**
- Create: `web/src/components/FeedbackModal.tsx`
- Create: `web/src/pages/Notes.tsx`
- Modify: `web/src/App.tsx` (`/notes`, `/notes/:id` 교체)

**Interfaces:**
- Consumes: `api.listRecords`, `api.getRecord`, `api.feedback`, RecordCard(resolutionLabel), store(`newSession`)
- Produces: 상세 화면 버튼 2개 — "실험 피드백"(모달) / "후속 실험 기록"(`newSession("followup", baseId)` 생성 후 `#/followup/:sid` 이동, Task 9가 이 세션 규약을 소비)

- [ ] **Step 1: FeedbackModal.tsx**

```tsx
import { useState } from "react";
import { api } from "../api";
import type { RecordDetail } from "../types";

export default function FeedbackModal({ detail, onClose, onDone }: {
  detail: RecordDetail; onClose: () => void; onDone: () => void;
}) {
  const [resolved, setResolved] = useState(true);
  const [cause, setCause] = useState(detail.record.resolution.actual_cause ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.feedback(detail.record.id, resolved, cause.trim() || undefined, note);
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="w-96 rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold">실험 피드백 — {detail.record.id}</div>
        <p className="mt-1 text-xs text-slate-500">과거 실험의 해결 여부·확정 원인을 갱신합니다.</p>
        <div className="mt-4 flex gap-2">
          {[true, false].map((v) => (
            <button key={String(v)} onClick={() => setResolved(v)}
              className={`rounded-full border px-4 py-1.5 text-sm ${resolved === v ? "border-blue-600 bg-blue-50 font-medium text-blue-700" : "border-slate-300"}`}>
              {v ? "해결됨" : "미해결"}
            </button>
          ))}
        </div>
        {resolved && (
          <div className="mt-4">
            <div className="text-xs text-slate-400">확정 원인</div>
            <div className="mt-1 flex flex-wrap gap-2">
              {detail.record.suspected_causes.map((c) => (
                <button key={c.cause} onClick={() => setCause(c.cause)}
                  className={`rounded-full border px-3 py-1 text-sm ${cause === c.cause ? "border-blue-600 bg-blue-50" : "border-slate-300"}`}>
                  {c.cause}
                </button>
              ))}
            </div>
            <input value={cause} onChange={(e) => setCause(e.target.value)} placeholder="직접 입력"
              className="mt-2 w-full rounded border border-slate-300 px-2 py-1.5 text-sm" />
          </div>
        )}
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="메모 (선택)"
          className="mt-3 w-full rounded border border-slate-300 px-2 py-1.5 text-sm" />
        {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">취소</button>
          <button onClick={submit} disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-40">반영</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Notes.tsx**

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import FeedbackModal from "../components/FeedbackModal";
import { resolutionLabel } from "../components/RecordCard";
import { newSession, saveSession } from "../store";
import type { RecordDetail, RecordMeta } from "../types";

export default function Notes() {
  const { id } = useParams();
  const nav = useNavigate();
  const [records, setRecords] = useState<RecordMeta[]>([]);
  const [q, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [modal, setModal] = useState(false);

  const loadList = () => api.listRecords().then((r) => setRecords(r.records));
  useEffect(() => { void loadList(); }, []);
  useEffect(() => {
    if (id) api.getRecord(id).then(setDetail).catch(() => setDetail(null));
    else setDetail(null);
  }, [id]);

  const filtered = records.filter((r) =>
    [r.id, r.experiment_type, r.objective, ...r.equipment, ...r.materials, r.symptom.description]
      .join(" ").toLowerCase().includes(q.toLowerCase())
    && (!from || r.date >= from) && (!to || r.date <= to));  // 기간 필터 (ISO 날짜 문자열 비교)

  function startFollowup() {
    const s = newSession("followup", detail!.record.id);
    s.title = `후속: ${detail!.record.experiment_type || detail!.record.id}`;
    saveSession(s);
    nav(`/followup/${s.id}`);
  }

  return (
    <div className="flex h-screen">
      <div className="w-80 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-4">
        <div className="text-lg font-bold">연구노트</div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="기록 검색 (장비·재료·증상...)"
          className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
        <div className="mt-2 flex items-center gap-1 text-xs">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="min-w-0 flex-1 rounded border border-slate-200 px-2 py-1" />
          <span className="text-slate-400">~</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="min-w-0 flex-1 rounded border border-slate-200 px-2 py-1" />
          {(from || to) && (
            <button onClick={() => { setFrom(""); setTo(""); }} className="text-slate-400 hover:text-slate-600">✕</button>
          )}
        </div>
        <div className="mt-3 space-y-2">
          {filtered.map((r) => {
            const label = resolutionLabel(r);
            return (
              <button key={r.id} onClick={() => nav(`/notes/${r.id}`)}
                className={`w-full rounded-lg border p-3 text-left ${id === r.id ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}>
                <div className="text-xs text-blue-600">{r.id}</div>
                <div className="truncate text-sm font-medium">{r.objective || r.experiment_type || "(제목 없음)"}</div>
                <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${label.cls}`}>{label.text}</span>
              </button>
            );
          })}
          {filtered.length === 0 && <div className="text-sm text-slate-400">기록 없음</div>}
        </div>
      </div>
      <div className="min-w-0 flex-1 overflow-y-auto p-8">
        {!detail && <div className="text-slate-400">왼쪽에서 기록을 선택하세요.</div>}
        {detail && (
          <div className="mx-auto max-w-3xl">
            <div className="text-xs font-medium text-blue-600">{detail.record.id}</div>
            <h1 className="mt-1 text-2xl font-bold">{detail.record.objective || detail.record.experiment_type}</h1>
            <div className="mt-1 text-sm text-slate-500">
              {detail.record.date} · {detail.record.experiment_type}
              {detail.record.needs_review && <span className="ml-2 rounded bg-red-100 px-2 py-0.5 text-xs text-red-700">검토 필요</span>}
            </div>
            {detail.record.followup_of && (
              <button onClick={() => nav(`/notes/${detail.record.followup_of}`)}
                className="mt-2 text-sm text-blue-600 underline">
                ← 기준 실험: {detail.record.followup_of}
              </button>
            )}
            <div className="mt-5 grid grid-cols-4 gap-3 rounded-xl bg-slate-100 p-4 text-sm">
              <div><div className="text-xs text-slate-400">장비</div>{detail.record.equipment.join(", ") || "-"}</div>
              <div><div className="text-xs text-slate-400">재료</div>{detail.record.materials.join(", ") || "-"}</div>
              <div><div className="text-xs text-slate-400">증상</div>{detail.record.symptom.category === "none" ? "문제 없음" : detail.record.symptom.category}</div>
              <div><div className="text-xs text-slate-400">해결</div>{resolutionLabel(detail.record).text}</div>
            </div>
            {detail.record.parameters.length > 0 && (
              <div className="mt-4">
                <div className="font-semibold">공정변수</div>
                <div className="mt-1 flex flex-wrap gap-2 text-sm">
                  {detail.record.parameters.map((p) => (
                    <span key={p.name} className="rounded bg-white px-2 py-1 shadow-sm">{p.name} = {p.value}</span>
                  ))}
                </div>
              </div>
            )}
            {detail.record.suspected_causes.length > 0 && (
              <div className="mt-4">
                <div className="font-semibold">원인 후보</div>
                {detail.record.suspected_causes.map((c) => (
                  <div key={c.cause} className="mt-1 text-sm">
                    {c.status === "confirmed" ? "✅" : c.status === "rejected" ? "❌" : "◻"} {c.cause}
                    <span className="ml-1 text-xs text-slate-400">({c.status})</span>
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4">
              <div className="font-semibold">본문</div>
              <pre className="mt-2 whitespace-pre-wrap rounded-xl bg-white p-4 text-sm shadow-sm">{detail.body}</pre>
            </div>
            <div className="mt-6 flex gap-3">
              <button onClick={() => setModal(true)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-50">
                실험 피드백
              </button>
              <button onClick={startFollowup}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
                후속 실험 기록
              </button>
            </div>
          </div>
        )}
      </div>
      {modal && detail && (
        <FeedbackModal detail={detail} onClose={() => setModal(false)}
          onDone={() => { setModal(false); api.getRecord(detail.record.id).then(setDetail); void loadList(); }} />
      )}
    </div>
  );
}
```

- [ ] **Step 3: App.tsx 라우트 교체 + 검증 1회 + 커밋**

```tsx
import Notes from "./pages/Notes";
<Route path="/notes" element={<Notes />} />
<Route path="/notes/:id" element={<Notes />} />
```

```bash
cd web && npm run build
cd .. && git add -A && git commit -m "feat: 연구노트 — 목록·검색·상세·실험 피드백 모달"
```

---

### Task 9: ⑦ 후속 실험 기록 — 기준 패널 + 변수 diff

**Files:**
- Create: `web/src/components/DiffPanel.tsx`
- Create: `web/src/components/DiffPanel.test.tsx`
- Create: `web/src/pages/FollowUp.tsx`
- Modify: `web/src/App.tsx` (`/followup/:sid` 교체)

**Interfaces:**
- Consumes: LogChat과 동일한 루프 로직(코드 재사용 위해 LogChat을 그대로 임베드하지 않고, FollowUp이 LogChat과 동일 규약의 세션을 사용하며 좌측에 기준 패널·우측 구조화 패널 대신 diff 패널을 추가로 렌더), `api.getRecord`, Task 6 Preview의 baseId 규약
- Produces: `toEntries(equipment, materials, parameters) -> Parameter[]` (장비·재료를 이름=값
  항목으로 합쳐 parameters와 함께 비교 — 스펙 ⑦의 3종 diff), `diffParameters(base, current)
  -> {changed, kept, added}` (둘 다 DiffPanel export — 테스트 대상)

- [ ] **Step 1: DiffPanel.tsx**

```tsx
import type { ParsedLog, Parameter, RecordDetail } from "../types";

export interface ParamDiff {
  changed: { name: string; from: string; to: string }[];
  kept: { name: string; value: string }[];
  added: { name: string; value: string }[];
}

/** 스펙 ⑦: 장비·재료·parameters 3종을 이름=값 항목으로 통합해 한 번에 비교 */
export function toEntries(
  equipment: string[], materials: string[], parameters: Parameter[],
): Parameter[] {
  return [
    { name: "장비", value: equipment.join(", "), controllable: true },
    { name: "재료", value: materials.join(", "), controllable: true },
    ...parameters,
  ];
}

export function diffParameters(base: Parameter[], current: Parameter[]): ParamDiff {
  const baseMap = new Map(base.map((p) => [p.name, p.value]));
  const out: ParamDiff = { changed: [], kept: [], added: [] };
  for (const p of current) {
    const bv = baseMap.get(p.name);
    if (bv === undefined) out.added.push({ name: p.name, value: p.value });
    else if (bv !== p.value) out.changed.push({ name: p.name, from: bv, to: p.value });
    else out.kept.push({ name: p.name, value: p.value });
  }
  return out;
}

export default function DiffPanel({ base, current }: {
  base: RecordDetail; current: ParsedLog | null;
}) {
  const diff = current
    ? diffParameters(
        toEntries(base.record.equipment, base.record.materials, base.record.parameters),
        toEntries(current.equipment, current.materials, current.parameters))
    : null;
  return (
    <div className="mt-4">
      <div className="text-xs text-slate-400">기준 대비 변수 비교</div>
      {!diff && <div className="mt-1 text-sm text-slate-400">기록을 입력하면 자동 비교됩니다.</div>}
      {diff && (
        <div className="mt-2 space-y-1 text-sm">
          {diff.changed.map((d) => (
            <div key={d.name} data-testid="diff-changed" className="rounded bg-blue-50 px-2 py-1">
              🔵 <b>{d.name}</b>: {d.from} ➔ {d.to}
            </div>
          ))}
          {diff.added.map((d) => (
            <div key={d.name} className="rounded bg-purple-50 px-2 py-1">🟣 <b>{d.name}</b>: {d.value} (신규)</div>
          ))}
          {diff.kept.map((d) => (
            <div key={d.name} data-testid="diff-kept" className="rounded bg-emerald-50 px-2 py-1">
              🟢 {d.name}: {d.value} (유지)
            </div>
          ))}
          {diff.changed.length === 0 && diff.added.length === 0 && (
            <div className="text-amber-600">변경된 변수가 없습니다 — 후속 실험은 보통 변수 하나를 바꿉니다.</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: FollowUp.tsx**

LogChat과 동일한 루프(파싱·gap 질문·재파싱)를 쓰되 화면 구성이 다르므로 별도 페이지.
루프 로직은 LogChat.tsx에서 그대로 복사하지 말고, **LogChat.tsx의 루프 부분(runParse/onSend/onSaveRaw와 상태)을 `web/src/useLogLoop.ts` 훅으로 추출**해 둘이 공유한다 (이 스텝에서 추출 리팩터 포함 — LogChat.tsx는 훅 호출로 축소).

`web/src/useLogLoop.ts`:

```ts
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { getSession, saveSession } from "./store";
import type { Session } from "./types";

const MAX_ROUNDS = 3;

function chipsFor(gap: string): string[] {
  const chips = ["건너뛰기"];
  if (gap.includes("증상")) chips.unshift("문제 없음");
  return chips;
}

export function useLogLoop(sid: string | undefined) {
  const nav = useNavigate();
  const [session, setSession] = useState<Session | null>(() => getSession(sid ?? "") ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requiredTotal, setRequiredTotal] = useState(5);
  const started = useRef(false);

  useEffect(() => {
    api.config().then((c) =>
      setRequiredTotal(c.required_fields.length + c.required_parameters.length));
  }, []);

  function update(s: Session) {
    saveSession(s);
    setSession({ ...s });
  }

  async function runParse(s: Session) {
    setBusy(true);
    setError(null);
    try {
      const { parsed, gaps } = await api.parse(s.rawText);
      s.parsed = parsed;
      s.gaps = gaps;
      s.gapIndex = 0;
      s.answers = [];
      if (parsed.experiment_type || parsed.objective)
        s.title = (s.kind === "followup" ? "후속: " : "") +
          (parsed.experiment_type || parsed.objective.slice(0, 30));
      if (gaps.length > 0 && s.rounds < MAX_ROUNDS) {
        s.messages.push({ role: "ai", text: gaps[0], chips: chipsFor(gaps[0]) });
      } else if (gaps.length === 0) {
        s.messages.push({ role: "ai", text: "필요한 정보가 모두 채워졌습니다. 검토 후 저장하세요." });
      } else {
        s.messages.push({ role: "ai", text: `아직 ${gaps.length}개 항목이 비어 있지만 재질문을 마칩니다. 검토 후 저장하세요.` });
      }
      update(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    if (session.rawText && session.messages.length === 0) {
      session.messages.push({ role: "user", text: session.rawText });
      void runParse(session);
    }
  }, [session]);

  async function onSend(text: string) {
    const s = session!;
    s.messages.push({ role: "user", text });
    if (!s.parsed) {
      s.rawText = s.rawText ? `${s.rawText}\n${text}` : text;
      update(s);
      await runParse(s);
      return;
    }
    if (text !== "건너뛰기") s.answers.push(text);
    s.gapIndex += 1;
    if (s.gapIndex < s.gaps.length) {
      const g = s.gaps[s.gapIndex];
      s.messages.push({ role: "ai", text: g, chips: chipsFor(g) });
      update(s);
      return;
    }
    if (s.answers.length === 0) {
      // gaps는 지우지 않는다 — 게이지 정직성 유지, 저장 허용은 canSave가 판단
      s.messages.push({ role: "ai", text: "확인했습니다. 누락된 항목은 비운 채로 저장됩니다." });
      update(s);
      return;
    }
    s.rawText += `\n\n[추가 답변]\n${s.answers.join("\n")}`;
    s.rounds += 1;
    update(s);
    await runParse(s);
  }

  async function onSaveRaw() {
    const s = session!;
    const { id } = await api.saveRaw(s.rawText);
    s.saved = true;
    update(s);
    nav(`/notes/${id}`);
  }

  // 질문 루프를 끝냈거나 재질문 라운드를 소진해야 저장 진입 (스펙 ②)
  const canSave = !!session &&
    (session.gapIndex >= session.gaps.length || session.rounds >= MAX_ROUNDS);

  return { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse };
}
```

`web/src/pages/FollowUp.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import DiffPanel from "../components/DiffPanel";
import { resolutionLabel } from "../components/RecordCard";
import StructurePanel from "../components/StructurePanel";
import { useLogLoop } from "../useLogLoop";
import type { RecordDetail } from "../types";

export default function FollowUp() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse } = useLogLoop(sid);
  const [base, setBase] = useState<RecordDetail | null>(null);

  useEffect(() => {
    if (session?.baseId) api.getRecord(session.baseId).then(setBase).catch(() => {});
  }, [session?.baseId]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  return (
    <div className="flex h-screen">
      <div className="w-72 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-5">
        <div className="text-lg font-bold">기준 실험</div>
        {!base && <div className="mt-3 text-sm text-slate-400">기준 레코드 로딩...</div>}
        {base && (
          <>
            <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50 p-3">
              <div className="text-xs font-medium text-blue-600">{base.record.id}</div>
              <div className="mt-1 text-sm font-medium">{base.record.objective || base.record.experiment_type}</div>
              <span className={`mt-2 inline-block rounded-full px-2 py-0.5 text-xs ${resolutionLabel(base.record).cls}`}>
                {resolutionLabel(base.record).text}
              </span>
            </div>
            <DiffPanel base={base} current={session.parsed} />
            <button onClick={() => nav(`/notes/${base.record.id}`)}
              className="mt-5 w-full rounded-lg border border-slate-300 py-2 text-sm hover:bg-slate-50">
              기준 기록 열기
            </button>
          </>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">{session.baseId}에서 이어짐</div>
        </header>
        {error && (
          <div className="flex gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} onSend={onSend} busy={busy}
            placeholder="후속 실험 내용을 입력하세요 (무엇을 바꿨고 결과가 어땠는지)" />
        </div>
      </div>
      <StructurePanel parsed={session.parsed} gaps={session.gaps} canSave={canSave}
        requiredTotal={requiredTotal} saveLabel="검토 후 저장"
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}
```

`LogChat.tsx`를 훅 사용으로 축소 (루프 로직 제거, `useLogLoop` 호출 + 기존 레이아웃 유지 — 렌더 부분은 기존 그대로, 상태·핸들러만 훅에서):

```tsx
import { useNavigate, useParams } from "react-router-dom";
import ChatPane from "../components/ChatPane";
import StructurePanel from "../components/StructurePanel";
import { useLogLoop } from "../useLogLoop";

export default function LogChat() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse } = useLogLoop(sid);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">연구 기록</div>
        </header>
        {error && (
          <div className="flex items-center gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장 (needs_review)</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} onSend={onSend} busy={busy} />
        </div>
      </div>
      <StructurePanel parsed={session.parsed} gaps={session.gaps} canSave={canSave}
        requiredTotal={requiredTotal} saveLabel="검토 후 저장"
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}
```

- [ ] **Step 3: DiffPanel.test.tsx (스펙 지정 최소 테스트 ②)**

```tsx
import { diffParameters, toEntries } from "./DiffPanel";

test("변경·유지·신규 변수를 구분한다", () => {
  const base = [
    { name: "온도", value: "250C", controllable: true },
    { name: "전구체", value: "TMA(개봉 7일)", controllable: true },
  ];
  const current = [
    { name: "온도", value: "250C", controllable: true },
    { name: "전구체", value: "TMA(신규)", controllable: true },
    { name: "압력", value: "1Torr", controllable: true },
  ];
  const d = diffParameters(base, current);
  expect(d.kept).toEqual([{ name: "온도", value: "250C" }]);
  expect(d.changed).toEqual([{ name: "전구체", from: "TMA(개봉 7일)", to: "TMA(신규)" }]);
  expect(d.added).toEqual([{ name: "압력", value: "1Torr" }]);
});

test("장비·재료 변경도 diff에 잡힌다 (스펙 ⑦)", () => {
  const d = diffParameters(
    toEntries(["ALD-02"], ["TMA"], []),
    toEntries(["ALD-03"], ["TMA"], []));
  expect(d.changed).toEqual([{ name: "장비", from: "ALD-02", to: "ALD-03" }]);
  expect(d.kept).toEqual([{ name: "재료", value: "TMA" }]);
});
```

- [ ] **Step 4: App.tsx 라우트 교체 + 검증 1회 + 커밋**

```tsx
import FollowUp from "./pages/FollowUp";
<Route path="/followup/:sid" element={<FollowUp />} />
```

```bash
cd web && npx vitest run src/components && npm run build
cd .. && git add -A && git commit -m "feat: 후속 실험 — 기준 패널·변수 diff·useLogLoop 훅 공유"
```

---

### Task 10: 통합 — 정적 서빙 확인 + README

**Files:**
- Modify: `README.md` (웹 UI 섹션)

**Interfaces:**
- Consumes: 전 태스크 산출물.

- [ ] **Step 1: README에 웹 UI 섹션 추가**

`## 사용` 섹션 명령 목록에 한 줄 추가:

```
horcrux serve         # 웹 UI (LAB GENE) — http://127.0.0.1:8765
```

그 아래 새 섹션:

```markdown
## 웹 UI (LAB GENE)

    pip install -e ".[web]"
    cd web && npm install && npm run build && cd ..
    horcrux serve

브라우저에서 http://127.0.0.1:8765 접속. 기록/질문/연구노트/실험 피드백/후속 실험을
브라우저에서 수행한다 (CLI·디스코드 봇과 같은 볼트 공유).
개발 모드: `horcrux serve` + `cd web && npm run dev` (vite가 /api 프록시).
```

- [ ] **Step 2: 통합 검증 1회 (수동 스모크 — 유일한 수동 절차)**

```bash
cd web && npm run build && cd ..
python -m pytest -q --basetemp=.pytest_tmp
```

`horcrux serve` 실행 → 브라우저에서: 기록 1건 저장 → 연구노트에서 확인 → ask 1회 → 피드백 1회. (LLM provider 로그인 필요 — claude 권장.)

- [ ] **Step 3: 커밋**

```bash
git add -A && git commit -m "docs: 웹 UI 실행 안내"
```

---

## Self-Review 결과 반영 노트

- Task 5의 LogChat.tsx는 Task 9에서 `useLogLoop` 훅으로 리팩터된다 — Task 5 시점 코드는 완전 동작하며, Task 9가 동일 로직을 훅으로 추출한다 (중복 없이 공유하기 위한 순서 의존).
- `StructurePanel`의 `gaps` prop은 **마지막 파싱 기준 전체**다. 답변 진행만으로 게이지가
  차오르면 재파싱 전까지 거짓 100%가 되므로, 게이지는 파싱 결과만 반영하고 저장 허용은
  별도 `canSave`(질문 루프 소진 또는 라운드 소진)가 판단한다.
- 세션 스토어 v1 스키마 변경 시 `labgene.sessions.v1` 키 버전을 올려 마이그레이션 없이 폐기.

## 검증 워크플로 반영 (2026-08-01, 에이전트 28개)

계획 초안을 4개 렌즈(스펙 커버리지·백엔드 정확성·프론트 정확성·흐름 정합)로 리뷰 후
적대적 검증. 확정 결함 전부 반영 완료:

1. `toBeDisabled()`는 jest-dom 매처 — 의존성·셋업 없어 Task 5의 vitest·`tsc -b` 둘 다 실패
   (이후 모든 태스크 빌드로 전파). 내장 매처로 교체.
2. `test_followup_of_roundtrip`이 미임포트 `record_path` 사용 — import 추가 지시 명시.
3. ⑦ diff가 parameters만 비교 — 스펙은 장비·재료 포함 3종. `toEntries`로 통합.
4. 저장 버튼이 `!parsed`로만 게이팅 — 질문 루프 중에도 저장 진입 가능했음. `canSave` 추가.
5. 전부 건너뛰기 시 `gaps=[]` 클리어로 게이지가 거짓 100% — 클리어 제거.
6. 근거 배너가 records 단 무표시(2단) — records 배너 추가로 3단 완성.
7. ④ 폼에 `suspected_causes`·`symptom.category` 편집 없음 — 저장 후 수정 경로가 없어 추가.
8. feedback 실패 후 재시도 시 레코드 중복 생성 — `savedId` 가드.
9. 저장 완료 세션 재진입 시 중복 저장 경로 — Preview에서 차단.
10. 홈 미완료 목록이 최신 1건만 진입 가능 — 목록 렌더로 수정.
11. ⑤ 기간 필터 부재 — date 범위 입력 추가.
12. 스펙 지정 "② 칩 흐름" 테스트 부재 — `ChatPane.test.tsx` 추가.
13. `dist` 경로가 `-e` 설치 전제 — 주석으로 명시(wheel/exe는 2차).

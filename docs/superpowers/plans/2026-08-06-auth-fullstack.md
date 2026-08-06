# 인증·온보딩 풀스택 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배포 모드에서 구글 로그인→온보딩→연구실 컨텍스트 사용이 가능하게 하고, 참고문헌 백엔드를 붙여 frontend 브랜치를 main에 머지 가능한 상태로 만든다.

**Architecture:** 스펙 `docs/superpowers/specs/2026-08-06-auth-frontend-design.md`. 백엔드는 병합본(08dfdfd)의 기존 패턴(DeployCtx, lab_cfg, update_resolution) 재사용. 프론트는 AuthProvider가 무인증 `GET /api/auth-config`로 부팅해 로컬/배포 분기, 로그인·온보딩은 라우트가 아니라 **게이트**(앱 셸 대신 렌더)로 구현 — HashRouter 라우트 추가 없이 같은 UX.

**Tech Stack:** 기존 + `@supabase/supabase-js`(신규 의존성 1개, 공식 SDK). supabase-js v2는 PKCE 기본이라 OAuth 복귀가 `?code=` 쿼리로 와서 HashRouter의 `#/`와 충돌하지 않는다.

## Global Constraints

- 작업 위치 `.claude/worktrees/web-impl`, 태스크마다 frontend 브랜치 커밋+푸시.
- 검증 최소화(사용자 지시): 태스크당 체크 1회. pytest는 `--basetemp=.pytest_tmp` 필수.
- 로컬 모드(`SUPABASE_URL` 없음) 동작 무변경 — 모든 신규 UI는 deploy 모드에서만.
- `llm_credential`은 어떤 응답에도 싣지 않는다 (`_lab_out` 화이트리스트 유지).
- 크레덴셜 폼은 write-only. 429 전역 배너 없음(서버 detail을 기존 에러 표시로).
- main 머지는 로컬 배포 모드 E2E 후에만 (계획 밖 — 사용자 Supabase 값 필요).

---

### Task 0: main 머지 + 베이스라인

**Files:** (머지만, 신규 파일 없음)

- [ ] **Step 1: origin/main을 frontend에 머지**

```bash
cd .claude/worktrees/web-impl
git fetch origin && git merge origin/main
```

충돌 예상 없음(백엔드는 src·docs, 우리는 web·docs 서로 다른 파일). 충돌 시 양쪽 보존.

- [ ] **Step 2: 의존성 재설치 + 베이스라인 1회**

```bash
pip install -e ".[dev]"
python -m pytest --basetemp=.pytest_tmp -q
cd web && npx vitest run
```

Expected: 전부 통과 (실패 시 pyjwt 등 누락 — `pip install -e ".[dev,deploy]"`로 재시도).

- [ ] **Step 3: 커밋 + 푸시**

```bash
git commit -m "merge: main(백엔드 배포 모드) 반영" # 머지 커밋이 이미 있으면 생략
git push origin frontend
```

---

### Task 1: 백엔드 — 참고문헌 저장

**Files:**
- Modify: `src/horcrux/records.py` (Reference 모델 + 필드)
- Modify: `src/horcrux/server.py` (_META_KEYS, ReferencesIn, PUT 엔드포인트)
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `PUT /api/records/{id}/references` → `{"record": <meta>}` — 프론트 `api.putReferences`가 이미 이 형태를 기대.

- [ ] **Step 1: records.py — Symptom 클래스 아래에 추가**

```python
class Reference(BaseModel):
    # Literal이 아니라 str — 나중에 "pdf" 타입이 추가돼도 구버전이 신버전 md를
    # 읽다 검증 실패하지 않게 느슨하게 둔다. UI가 3종(paper|link|record)만 만든다.
    type: str = "link"
    title: str = ""
    url: str = ""          # DOI는 프론트가 https://doi.org/... 로 정규화해서 보냄
    record_id: str = ""    # record 타입만 사용
```

`ExperimentRecord`의 `notes` 필드 아래에:

```python
    references: list[Reference] = Field(default_factory=list)
```

- [ ] **Step 2: server.py — _META_KEYS 끝에 "references" 추가, FeedbackIn 아래 입력 모델**

```python
_META_KEYS = ("id", "date", "experiment_type", "objective", "equipment", "materials",
              "symptom", "resolution", "needs_review", "followup_of", "references")


class ReferencesIn(BaseModel):
    references: list[Reference]      # from .records import Reference 추가
```

api_feedback 아래 엔드포인트 (api_feedback과 동일 패턴 — lab_cfg·lab_lock 경유):

```python
    @app.put("/api/records/{record_id}/references")
    def api_put_references(record_id: str, inp: ReferencesIn, ctx=Depends(require_lab)):
        c = lab_cfg(ctx)
        p = record_path(c.vault, record_id)
        if not p.exists():
            raise HTTPException(404, f"레코드 없음: {record_id}")
        with lab_lock(ctx):
            rec, body = load_record(p)
            rec.references = inp.references
            write_md(p, rec.model_dump(), body)   # body 보존 — update_resolution과 동일
        return {"record": _meta(rec)}
```

import에 `write_md` 추가 (`from .records import ...`).

- [ ] **Step 3: tests/test_server.py — 기존 client 픽스처 사용해 3케이스**

```python
def test_references_roundtrip(client):
    rid = client.post("/api/records", json=_record_payload()).json()["id"]
    refs = [{"type": "paper", "title": "ALD 논문", "url": "https://doi.org/10.1/x", "record_id": ""},
            {"type": "record", "title": "", "url": "", "record_id": rid}]
    r = client.put(f"/api/records/{rid}/references", json={"references": refs})
    assert r.status_code == 200
    assert r.json()["record"]["references"] == refs
    detail = client.get(f"/api/records/{rid}").json()
    assert detail["record"]["references"] == refs
    assert "원문 로그" in detail["body"]          # body 보존

def test_references_missing_record(client):
    assert client.put("/api/records/없는것/references",
                      json={"references": []}).status_code == 404

def test_legacy_record_has_empty_references(client):
    rid = client.post("/api/records", json=_record_payload()).json()["id"]
    assert client.get("/api/records").json()["records"][0]["references"] == []
```

(`_record_payload()`는 기존 테스트의 저장 페이로드 헬퍼 — 파일에 이미 있는 것을 재사용,
없으면 기존 저장 테스트의 json 인자를 그대로 복사해 헬퍼로 추출)

- [ ] **Step 4: 체크 1회** — `python -m pytest --basetemp=.pytest_tmp -q` Expected: 통과

- [ ] **Step 5: 커밋 + 푸시** — `git add src tests && git commit -m "feat: 참고문헌 저장 — Reference 모델·PUT 엔드포인트·메타 확장" && git push origin frontend`

---

### Task 2: 백엔드 — auth-config + labs/me 확장

**Files:**
- Modify: `src/horcrux/server.py` (auth-config 엔드포인트, api_lab_me 확장)
- Modify: `src/horcrux/labs.py` (get_usage, list_members)
- Test: `tests/test_server.py` (FakeDB 메서드 + 2케이스)

**Interfaces:**
- Produces: `GET /api/auth-config` → `{"deploy": bool, "supabase_url": str|null, "supabase_anon_key": str|null}` (무인증)
- Produces: `GET /api/labs/me` → 기존 + `"usage_today": int` + admin일 때 `"members": [{"user_id", "email", "role"}]`

- [ ] **Step 1: labs.py — LabsDB에 메서드 2개**

```python
    def get_usage(self, lab_id: str) -> int:
        day = datetime.date.today().isoformat()
        rows = (self._c.table("llm_usage").select("*")
                .eq("lab_id", lab_id).eq("day", day).execute().data)
        return rows[0]["count"] if rows else 0

    def list_members(self, lab_id: str) -> list[dict]:
        ms = self._c.table("lab_members").select("*").eq("lab_id", lab_id).execute().data
        out = []
        for m in ms:
            try:
                u = self._c.auth.admin.get_user_by_id(m["user_id"])
                email = u.user.email or m["user_id"]
            except Exception:               # auth 조회 실패해도 목록은 나가게
                email = m["user_id"]
            out.append({"user_id": m["user_id"], "email": email, "role": m["role"]})
        return out
```

- [ ] **Step 2: server.py — 무인증 auth-config (api_config 위에) + api_lab_me 확장**

```python
    @app.get("/api/auth-config")
    def api_auth_config():
        # 유일한 무인증 엔드포인트 — 프론트 부팅용. anon key는 공개 전제 값.
        return {"deploy": deploy is not None,
                "supabase_url": os.environ.get("SUPABASE_URL"),
                "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY")}
```

api_lab_me 교체:

```python
    @app.get("/api/labs/me")
    def api_lab_me(ctx=Depends(require_lab)):
        if ctx is None:
            return {"lab": None, "role": None, "usage_today": 0}
        out = {"lab": _lab_out(ctx.lab, ctx.role), "role": ctx.role,
               "usage_today": deploy.db.get_usage(ctx.lab["id"])}
        if ctx.role == "admin":
            out["members"] = deploy.db.list_members(ctx.lab["id"])
        return out
```

- [ ] **Step 3: tests/test_server.py — 기존 FakeDB에 `get_usage`(고정 3)·`list_members`
  (관리자 1명 반환) 추가 후 2케이스**

```python
def test_auth_config_local(client):
    r = client.get("/api/auth-config").json()
    assert r["deploy"] is False and r["supabase_url"] is None

def test_lab_me_extended(deploy_client):   # 기존 배포 모드 픽스처명에 맞출 것
    r = deploy_client.get("/api/labs/me", headers=_auth_header()).json()
    assert r["usage_today"] == 3
    assert r["members"][0]["role"] == "admin"
```

(픽스처·헤더 헬퍼 이름은 test_server.py의 기존 배포 모드 테스트 것을 그대로 사용)

- [ ] **Step 4: 체크 1회** — `python -m pytest --basetemp=.pytest_tmp -q` Expected: 통과

- [ ] **Step 5: 커밋 + 푸시** — `git commit -m "feat: 무인증 auth-config + labs/me에 사용량·멤버 목록"`

---

### Task 3: 프론트 — AuthProvider·게이트·로그인·온보딩

**Files:**
- Create: `web/src/auth.tsx` (AuthProvider + resolveRoute + useAuth)
- Create: `web/src/pages/Login.tsx`, `web/src/pages/Onboarding.tsx`
- Modify: `web/src/api.ts` (Bearer 첨부 + 401/403 콜백 + labs API + authConfig)
- Modify: `web/src/types.ts` (AuthConfig·Lab·LabMe 타입)
- Modify: `web/src/App.tsx` (AuthProvider + 게이트 분기)
- Test: `web/src/auth.test.ts` (resolveRoute 4케이스)

**Interfaces:**
- Produces: `useAuth(): { mode, session, lab, role, usage, members, refreshLab, signOut }` — Task 4의 Settings·Sidebar가 사용.
- Produces: `resolveRoute(mode, session, lab): "login" | "onboarding" | "app"`

- [ ] **Step 1: 의존성** — `cd web && npm install @supabase/supabase-js`

- [ ] **Step 2: types.ts 끝에 추가**

```ts
export interface AuthConfig { deploy: boolean; supabase_url: string | null; supabase_anon_key: string | null }
export interface Lab {
  id: string; name: string; llm_mode: "central" | "own";
  llm_provider: string | null; daily_llm_limit: number; invite_code?: string;
}
export interface LabMember { user_id: string; email: string; role: string }
export interface LabMe { lab: Lab | null; role: "admin" | "member" | null; usage_today: number; members?: LabMember[] }
```

- [ ] **Step 3: api.ts — 토큰 주입·에러 분기·labs API**

http() 교체 및 하단 추가:

```ts
// AuthProvider가 등록 — api.ts가 Supabase·라우터를 직접 알지 않게 한다
let getToken: () => Promise<string | null> = async () => null;
let onAuthError: (status: 401 | 403) => void = () => {};
export function registerAuth(t: typeof getToken, e: typeof onAuthError) {
  getToken = t; onAuthError = e;
}

async function http<T>(method: string, url: string, body?: unknown): Promise<T> {
  const token = await getToken();
  const res = await fetch(url, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) onAuthError(res.status);
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `요청 실패 (${res.status})`);
  }
  return res.json() as Promise<T>;
}
```

api 객체에 추가:

```ts
  authConfig: () => http<AuthConfig>("GET", "/api/auth-config"),
  labMe: () => http<LabMe>("GET", "/api/labs/me"),
  labCreate: (name: string) => http<{ lab: Lab; role: string }>("POST", "/api/labs", { name }),
  labJoin: (invite_code: string) => http<{ lab: Lab; role: string }>("POST", "/api/labs/join", { invite_code }),
  labSettings: (patch: Partial<{ name: string; daily_llm_limit: number; llm_mode: string;
    llm_provider: string; llm_credential: string; rotate_invite: boolean }>) =>
    http<{ ok: boolean }>("PUT", "/api/labs/settings", patch),
```

- [ ] **Step 4: auth.tsx**

```tsx
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, registerAuth } from "./api";
import type { LabMe } from "./types";

export type AuthMode = "loading" | "local" | "deploy";

// 게이트 분기 — 순수 함수로 분리해 테스트한다
export function resolveRoute(mode: AuthMode, session: boolean, lab: boolean): "loading" | "login" | "onboarding" | "app" {
  if (mode === "loading") return "loading";
  if (mode === "local") return "app";
  if (!session) return "login";
  return lab ? "app" : "onboarding";
}

interface AuthState {
  mode: AuthMode;
  session: Session | null;
  me: LabMe | null;
  refreshLab: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}
const Ctx = createContext<AuthState>({
  mode: "local", session: null, me: null,
  refreshLab: async () => {}, signIn: async () => {}, signOut: async () => {},
});
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AuthMode>("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<LabMe | null>(null);
  const sb = useRef<SupabaseClient | null>(null);

  async function refreshLab() {
    try {
      setMe(await api.labMe());
    } catch {
      setMe(null);           // 403(무소속) 포함 — 게이트가 온보딩으로 보낸다
    }
  }

  useEffect(() => {
    let unsub = () => {};
    void (async () => {
      try {
        const cfg = await api.authConfig();
        if (!cfg.deploy || !cfg.supabase_url || !cfg.supabase_anon_key) {
          setMode("local");
          return;
        }
        const client = createClient(cfg.supabase_url, cfg.supabase_anon_key);
        sb.current = client;
        registerAuth(
          async () => (await client.auth.getSession()).data.session?.access_token ?? null,
          (status) => { if (status === 401) void client.auth.signOut(); },
        );
        const { data } = await client.auth.getSession();
        setSession(data.session);
        setMode("deploy");
        const sub = client.auth.onAuthStateChange((_e, s) => setSession(s));
        unsub = () => sub.data.subscription.unsubscribe();
      } catch {
        setMode("local");    // auth-config 실패(구버전 서버) — 기존 동작 유지
      }
    })();
    return unsub;
  }, []);

  useEffect(() => {
    if (mode === "deploy" && session) void refreshLab();
    if (!session) setMe(null);
  }, [mode, session]);

  return (
    <Ctx.Provider value={{
      mode, session, me, refreshLab,
      signIn: async () => {
        await sb.current?.auth.signInWithOAuth({
          provider: "google", options: { redirectTo: window.location.origin },
        });
      },
      signOut: async () => { await sb.current?.auth.signOut(); },
    }}>
      {children}
    </Ctx.Provider>
  );
}
```

- [ ] **Step 5: Login.tsx / Onboarding.tsx**

```tsx
// pages/Login.tsx
import { useAuth } from "../auth";

export default function Login() {
  const { signIn } = useAuth();
  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-50">
      <div className="w-80 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-xl text-white">⚗</span>
        <div className="mt-3 text-xl font-bold">LAB GENE</div>
        <p className="mt-1 text-sm text-slate-500">연구실 실험 기록·진단</p>
        <button onClick={() => void signIn()}
          className="mt-6 w-full rounded-lg border border-slate-300 py-2.5 text-sm font-medium hover:bg-slate-50">
          G 구글로 계속하기
        </button>
      </div>
    </div>
  );
}
```

```tsx
// pages/Onboarding.tsx
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

export default function Onboarding() {
  const { refreshLab, signOut } = useAuth();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(f: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await f(); await refreshLab(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md space-y-4">
        <div className="text-center text-xl font-bold">소속 연구실 설정</div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="font-semibold">연구실 만들기</div>
          <p className="mt-1 text-xs text-slate-500">새 연구실의 관리자가 됩니다.</p>
          <div className="mt-3 flex flex-col gap-2 md:flex-row">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="연구실 이름"
              className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" />
            <button onClick={() => void run(() => api.labCreate(name.trim()))} disabled={busy || !name.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-40">만들기</button>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="font-semibold">초대 코드로 합류</div>
          <p className="mt-1 text-xs text-slate-500">관리자에게 받은 코드를 입력하세요.</p>
          <div className="mt-3 flex flex-col gap-2 md:flex-row">
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="초대 코드"
              className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" />
            <button onClick={() => void run(() => api.labJoin(code.trim()))} disabled={busy || !code.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-40">합류</button>
          </div>
        </div>
        {error && <div className="text-center text-sm text-red-600">{error}</div>}
        <button onClick={() => void signOut()} className="w-full text-center text-xs text-slate-400 underline">
          다른 계정으로 로그인
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: App.tsx — AuthProvider로 감싸고 게이트 분기**

```tsx
import { AuthProvider, resolveRoute, useAuth } from "./auth";
import Login from "./pages/Login";
import Onboarding from "./pages/Onboarding";

function Gate({ children }: { children: ReactNode }) {
  const { mode, session, me } = useAuth();
  const route = resolveRoute(mode, !!session, !!me?.lab);
  if (route === "loading") return <div className="flex h-screen items-center justify-center text-slate-400">불러오는 중...</div>;
  if (route === "login") return <Login />;
  if (route === "onboarding") return <Onboarding />;
  return <>{children}</>;
}
```

`<HashRouter><AuthProvider><Gate><NavProvider>...` 순서로 감싼다 (기존 내용은 Gate 안).

- [ ] **Step 7: auth.test.ts**

```ts
import { describe, expect, it } from "vitest";
import { resolveRoute } from "./auth";

describe("resolveRoute", () => {
  it("로컬 모드는 항상 앱", () => expect(resolveRoute("local", false, false)).toBe("app"));
  it("배포 + 미로그인 → 로그인", () => expect(resolveRoute("deploy", false, false)).toBe("login"));
  it("배포 + 로그인 + 무소속 → 온보딩", () => expect(resolveRoute("deploy", true, false)).toBe("onboarding"));
  it("배포 + 로그인 + 소속 → 앱", () => expect(resolveRoute("deploy", true, true)).toBe("app"));
});
```

- [ ] **Step 8: 체크 1회** — `npx vitest run` Expected: 통과 (렌더 테스트는 auth-config fetch가 실패해도 local 모드로 떨어져 기존 테스트 무영향)

- [ ] **Step 9: 커밋 + 푸시** — `git commit -m "feat: AuthProvider·게이트 — 구글 로그인·온보딩 (로컬 모드 무변경)"`

---

### Task 4: 프론트 — 설정 화면·사이드바 연구실 카드

**Files:**
- Create: `web/src/pages/Settings.tsx`
- Modify: `web/src/App.tsx` (/settings 라우트)
- Modify: `web/src/components/Sidebar.tsx` (연구실 카드 + admin 설정 링크 + 로그아웃)
- Test: `web/src/pages/Settings.test.tsx` (렌더 1개)

**Interfaces:**
- Consumes: Task 3 `useAuth`, `api.labSettings`.

- [ ] **Step 1: Settings.tsx**

```tsx
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { MobileBar } from "../nav";

export default function Settings() {
  const { me, refreshLab } = useAuth();
  const lab = me?.lab;
  const [name, setName] = useState(lab?.name ?? "");
  const [limit, setLimit] = useState(lab?.daily_llm_limit ?? 200);
  const [mode, setMode] = useState<"central" | "own">(lab?.llm_mode ?? "central");
  const [provider, setProvider] = useState(lab?.llm_provider ?? "claude");
  const [credential, setCredential] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  if (!lab || me?.role !== "admin")
    return <div className="p-8 text-slate-500">관리자만 접근할 수 있습니다.</div>;

  const modeChangedToOwn = mode === "own" && lab.llm_mode !== "own";
  const canSave = !busy && !(modeChangedToOwn && !credential.trim());

  async function act(patch: Parameters<typeof api.labSettings>[0], done: string) {
    setBusy(true); setMsg(null);
    try { await api.labSettings(patch); await refreshLab(); setMsg(done); setCredential(""); }
    catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  }

  function save() {
    const patch: Parameters<typeof api.labSettings>[0] = {};
    if (name.trim() && name !== lab.name) patch.name = name.trim();
    if (limit !== lab.daily_llm_limit) patch.daily_llm_limit = limit;
    if (mode !== lab.llm_mode) patch.llm_mode = mode;
    if (mode === "own" && credential.trim()) {
      patch.llm_provider = provider;
      patch.llm_credential = credential.trim();
    }
    void act(patch, "저장했습니다");
  }

  return (
    <>
    <MobileBar title="연구실 설정" />
    <div className="mx-auto max-w-2xl space-y-4 px-5 py-6 md:px-8 md:py-8">
      <h1 className="text-xl font-bold md:text-2xl">연구실 설정</h1>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="text-xs text-slate-400">연구실 이름</div>
        <input value={name} onChange={(e) => setName(e.target.value)}
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm" />
        <div className="mt-4 text-xs text-slate-400">일일 LLM 사용 상한</div>
        <input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value))}
          className="mt-1 w-40 rounded border border-slate-300 px-3 py-2 text-sm" />
        <div className="mt-2 text-sm text-slate-500">
          오늘 사용량 {me.usage_today} / {lab.daily_llm_limit}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="font-semibold">초대 코드</div>
        <div className="mt-2 flex items-center gap-3">
          <code className="rounded bg-slate-100 px-3 py-1.5 text-sm">{lab.invite_code}</code>
          <button onClick={() => void act({ rotate_invite: true }, "재발급했습니다")} disabled={busy}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40">
            재발급
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="font-semibold">멤버</div>
        <div className="mt-2 space-y-1 text-sm">
          {(me.members ?? []).map((m) => (
            <div key={m.user_id} className="flex justify-between">
              <span className="truncate">{m.email}</span>
              <span className="text-slate-400">{m.role === "admin" ? "관리자" : "멤버"}</span>
            </div>
          ))}
          {!me.members?.length && <div className="text-slate-400">—</div>}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="font-semibold">LLM 모드</div>
        <div className="mt-2 flex gap-2">
          {(["central", "own"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`rounded-full border px-4 py-1.5 text-sm ${mode === m ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-300"}`}>
              {m === "central" ? "중앙 (기본)" : "연구실 크레덴셜"}
            </button>
          ))}
        </div>
        {mode === "own" && (
          <div className="mt-3 space-y-2">
            <select value={provider} onChange={(e) => setProvider(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm">
              <option value="claude">Claude 장기 토큰 (claude setup-token)</option>
              <option value="api">Anthropic API 키</option>
            </select>
            <input type="password" value={credential} onChange={(e) => setCredential(e.target.value)}
              placeholder={lab.llm_mode === "own" ? "등록됨 — 교체하려면 새 값 입력" : "토큰/키 입력"}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm" />
            <p className="text-xs text-slate-400">저장 후 값은 다시 표시되지 않습니다.</p>
          </div>
        )}
      </div>

      {msg && <div className="text-sm text-slate-600">{msg}</div>}
      <button onClick={save} disabled={!canSave}
        className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white disabled:opacity-40 md:w-auto md:px-8">
        저장
      </button>
    </div>
    </>
  );
}
```

- [ ] **Step 2: App.tsx 라우트 추가** — `<Route path="/settings" element={<Settings />} />`

- [ ] **Step 3: Sidebar.tsx — aside 하단(모바일 내비 링크 위)에 연구실 카드**

```tsx
// 컴포넌트 상단: const { mode, me, signOut } = useAuth();
// LINKS 렌더 시 admin이면 설정 링크 추가:
//   {me?.role === "admin" && <Link to="/settings" ...>⚙ 연구실 설정</Link>}
// aside 하단:
{mode === "deploy" && me?.lab && (
  <div className="border-t border-slate-200 p-3 text-sm">
    <div className="truncate font-medium">{me.lab.name}</div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-400">{me.role === "admin" ? "관리자" : "멤버"}</span>
      <button onClick={() => void signOut()} className="text-xs text-slate-400 underline">로그아웃</button>
    </div>
  </div>
)}
```

(설정 링크는 데스크톱 다크 레일·모바일 드로어 양쪽 navLinks에 조건부 추가)

- [ ] **Step 4: Settings.test.tsx**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Settings from "./Settings";

// useAuth를 모킹 — admin 컨텍스트
vi.mock("../auth", () => ({
  useAuth: () => ({
    me: { lab: { id: "l1", name: "산화막랩", llm_mode: "central", llm_provider: null,
                 daily_llm_limit: 200, invite_code: "abcd1234" },
          role: "admin", usage_today: 3, members: [{ user_id: "u1", email: "a@b.c", role: "admin" }] },
    refreshLab: async () => {},
  }),
}));
import { vi } from "vitest";

describe("Settings", () => {
  it("초대 코드·사용량·멤버를 렌더한다", () => {
    render(<Settings />);
    expect(screen.getByText("abcd1234")).toBeTruthy();
    expect(screen.getByText(/오늘 사용량 3/)).toBeTruthy();
    expect(screen.getByText("a@b.c")).toBeTruthy();
  });
});
```

(vi.mock 호이스팅 때문에 import 순서 주의 — vitest가 자동 호이스팅하므로 파일 상단 배치)

- [ ] **Step 5: 체크 1회** — `npx vitest run && npm run build` Expected: 통과 + 빌드 성공

- [ ] **Step 6: 커밋 + 푸시 (dist 포함)** — `git add web && git commit -m "feat: 연구실 설정 화면·사이드바 연구실 카드"`

---

### Task 5: 체크리스트 문서 + 최종 확인

**Files:**
- Create: `docs/deploy-checklist.md`

- [ ] **Step 1: 체크리스트 작성** — 사용자가 순서대로 진행할 대시보드 작업:
  1. supabase.com 프로젝트 생성 → Settings에서 URL·anon key·service_role key·JWT secret 확보
  2. 구글 클라우드 콘솔: OAuth 동의 화면(External) → 클라이언트 ID(웹) 생성,
     승인된 리디렉션 URI에 `https://<프로젝트>.supabase.co/auth/v1/callback` 등록
  3. Supabase Auth → Providers → Google에 클라이언트 ID·시크릿 입력.
     Auth → URL Configuration에 Site URL(Railway 도메인)과 `http://localhost:8765` 추가
  4. Supabase SQL Editor에서 `db/schema.sql` 실행
  5. 로컬 배포 모드 검증: PowerShell에서 `SUPABASE_URL`·`SUPABASE_SERVICE_KEY`·
     `SUPABASE_JWT_SECRET`·`SUPABASE_ANON_KEY`·`CRED_ENCRYPTION_KEY`(생성법 포함)·
     `ANTHROPIC_API_KEY`·`DATA_DIR` 설정 후 `horcrux serve` → 구글 로그인 E2E
  6. Railway: GitHub repo 연결(Dockerfile 자동 감지) → env 입력 → 볼륨 `/data` 마운트
  (각 단계에 정확한 클릭 경로·명령어 포함해 작성)

- [ ] **Step 2: 최종 체크 1회** — `python -m pytest --basetemp=.pytest_tmp -q && cd web && npx vitest run && npm run build`

- [ ] **Step 3: 커밋 + 푸시** — 체크리스트 + 잔여 변경. main 머지는 하지 않는다(E2E 후).

---

## 계획 밖 (사용자 Supabase 값 도착 후)

- 로컬 배포 모드 E2E: 구글 로그인 → 연구실 생성 → 기록 → 설정 저장
- 통과 시 frontend → main 머지·푸시 (참고문헌·인증 동시 활성화)

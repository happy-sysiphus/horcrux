# 참고문헌 프론트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 연구노트 상세에 참고문헌(논문·링크·내부 레코드) 섹션을 붙이고, DOI 자동 조회와 그래프 참조 엣지를 제공한다.

**Architecture:** 스펙 `docs/superpowers/specs/2026-08-06-references-design.md`의 프론트 파트. DOI 정규화·Crossref 조회는 순수 모듈(`refs.ts`)로 분리, UI는 `ReferencesSection` 컴포넌트 하나, 그래프는 기존 `buildGraph`에 엣지 규칙 추가. 백엔드(PUT 엔드포인트·메타 확장)는 backend 세션 담당 — 이 계획은 계약만 신뢰한다.

**Tech Stack:** React 18 + TS, Vite, vitest, Tailwind v4. 신규 의존성 없음.

## Global Constraints

- `src/horcrux/` 파이썬 파일 수정 금지 (backend 세션 담당).
- 작업 위치: `.claude/worktrees/web-impl`. 각 태스크 끝에 frontend 브랜치 커밋 + 푸시.
- **백엔드 미병합 상태에서도 크래시 금지**: API 응답에 `references`가 없을 수 있다 — 읽는 모든 곳에서 `?? []`. PUT 404는 에러 문구로 처리.
- 검증 최소화(사용자 지시): 태스크당 체크 1회(vitest 또는 build). TDD 사이클 생략.
- API 계약(스펙 확정): `PUT /api/records/{id}/references` body `{"references": [...]}` 응답 `{"record": <meta>}`. 계약 변경 금지.
- Reference 필드는 항상 4개 모두 전송: `{type, title, url, record_id}` (미사용 필드는 `""`).

---

### Task 1: DOI 모듈 (refs.ts)

**Files:**
- Create: `web/src/refs.ts`
- Test: `web/src/refs.test.ts`

**Interfaces:**
- Produces: `normalizeDoi(input: string): string | null`, `fetchDoiTitle(doiUrl: string): Promise<string>` — Task 3의 폼이 사용.

- [ ] **Step 1: refs.ts 작성**

```ts
// DOI 정규화·Crossref 제목 조회 — UI와 무관한 순수 모듈
export function normalizeDoi(input: string): string | null {
  const s = input.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  return /^10\.\S+\/\S+$/.test(s) ? `https://doi.org/${s}` : null;
}

// "제목 (성, 연도)" 조합. 실패는 throw — 호출부(폼)가 잡아 안내하고 수동 입력 지속.
export async function fetchDoiTitle(doiUrl: string): Promise<string> {
  const doi = doiUrl.replace("https://doi.org/", "");
  const res = await fetch(`https://api.crossref.org/works/${encodeURIComponent(doi)}`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) throw new Error(`조회 실패 (${res.status})`);
  const m = (await res.json()).message;
  const title: string = m.title?.[0] ?? "";
  if (!title) throw new Error("제목 정보 없음");
  const author: string | undefined = m.author?.[0]?.family;
  const year: number | undefined = m.issued?.["date-parts"]?.[0]?.[0];
  const suffix = author && year ? ` (${author}, ${year})` : author ? ` (${author})` : year ? ` (${year})` : "";
  return title + suffix;
}
```

- [ ] **Step 2: refs.test.ts 작성**

```ts
import { describe, expect, it } from "vitest";
import { normalizeDoi } from "./refs";

describe("normalizeDoi", () => {
  it("bare DOI를 doi.org URL로", () => {
    expect(normalizeDoi(" 10.1063/1.4757907 ")).toBe("https://doi.org/10.1063/1.4757907");
  });
  it("doi.org URL 붙여넣기 허용 (dx., http 포함)", () => {
    expect(normalizeDoi("https://dx.doi.org/10.1063/1.4757907")).toBe("https://doi.org/10.1063/1.4757907");
  });
  it("DOI 패턴이 아니면 null", () => {
    expect(normalizeDoi("https://example.com/manual.pdf")).toBeNull();
    expect(normalizeDoi("논문 제목")).toBeNull();
  });
});
```

(fetchDoiTitle은 외부 API라 단위 테스트 제외 — 스펙의 실패 처리로 충분)

- [ ] **Step 3: 체크 1회**

Run: `cd web && npx vitest run src/refs.test.ts`
Expected: 3 passed

- [ ] **Step 4: 커밋 + 푸시**

```bash
git add web/src/refs.ts web/src/refs.test.ts
git commit -m "feat: DOI 정규화·Crossref 제목 조회 모듈"
git push origin frontend
```

---

### Task 2: 타입·API 클라이언트·그래프 엣지

**Files:**
- Modify: `web/src/types.ts` (Reference 인터페이스 + RecordMeta.references)
- Modify: `web/src/api.ts` (putReferences)
- Modify: `web/src/graph.ts` (record 참조 엣지)
- Test: `web/src/graph.test.ts` (엣지 케이스 1개 추가)

**Interfaces:**
- Produces: `Reference { type, title, url, record_id }`, `api.putReferences(recordId: string, references: Reference[]): Promise<{ record: RecordMeta }>` — Task 3이 사용.

- [ ] **Step 1: types.ts에 추가**

`RecordMeta` 인터페이스 위에:

```ts
export interface Reference {
  type: "paper" | "link" | "record" | "pdf";  // pdf는 파일 첨부 스펙에서 사용 예정
  title: string;
  url: string;
  record_id: string;
}
```

`RecordMeta`에 필드 추가 (백엔드 병합 전 응답엔 없으므로 optional):

```ts
  references?: Reference[];
```

- [ ] **Step 2: api.ts에 추가** (`config:` 줄 위)

```ts
  putReferences: (recordId: string, references: Reference[]) =>
    http<{ record: RecordMeta }>("PUT", `/api/records/${recordId}/references`, { references }),
```

import에 `Reference` 추가.

- [ ] **Step 3: graph.ts 엣지 규칙 추가**

레코드 루프의 followup 처리 줄 바로 위에:

```ts
    // 참고문헌의 내부 레코드 참조 — 대상 존재·자기참조 제외, addLink가 dedup
    for (const ref of r.references ?? []) {
      if (ref.type === "record" && ref.record_id && ref.record_id !== r.id && expIds.has(ref.record_id))
        addLink(r.id, ref.record_id);
    }
```

- [ ] **Step 4: graph.test.ts에 케이스 추가**

```ts
  it("record 참조 엣지는 대상이 있을 때만, paper·자기참조·부재 대상은 무시", () => {
    const { links, nodes } = buildGraph([
      mk({ id: "a" }),
      mk({ id: "b", references: [
        { type: "record", record_id: "a", title: "", url: "" },
        { type: "record", record_id: "b", title: "", url: "" },
        { type: "record", record_id: "없는것", title: "", url: "" },
        { type: "paper", record_id: "", title: "논문", url: "https://doi.org/10.1/x" },
      ] }),
    ]);
    expect(links).toEqual([{ source: "b", target: "a" }]);
    expect(nodes.filter((n) => n.kind !== "exp")).toHaveLength(0); // paper는 노드 아님
  });
```

- [ ] **Step 5: 체크 1회**

Run: `cd web && npx vitest run src/graph.test.ts`
Expected: 6 passed (기존 5 + 신규 1)

- [ ] **Step 6: 커밋 + 푸시**

```bash
git add web/src/types.ts web/src/api.ts web/src/graph.ts web/src/graph.test.ts
git commit -m "feat: Reference 타입·putReferences API·그래프 참조 엣지"
git push origin frontend
```

---

### Task 3: ReferencesSection 컴포넌트 + 연구노트 통합

**Files:**
- Create: `web/src/components/ReferencesSection.tsx`
- Modify: `web/src/pages/Notes.tsx` (원인 후보 아래 섹션 삽입)
- Test: `web/src/components/ReferencesSection.test.tsx`

**Interfaces:**
- Consumes: Task 1 `normalizeDoi`/`fetchDoiTitle`, Task 2 `Reference`/`api.putReferences`.

- [ ] **Step 1: ReferencesSection.tsx 작성**

```tsx
import { useState } from "react";
import { api } from "../api";
import { fetchDoiTitle, normalizeDoi } from "../refs";
import type { RecordMeta, Reference } from "../types";

const ICON: Record<Reference["type"], string> = { paper: "📄", link: "🔗", record: "🧪", pdf: "📎" };
const TYPE_LABEL = { paper: "논문", link: "링크", record: "레코드" } as const;

export default function ReferencesSection({ recordId, references, records, onSaved, onOpenRecord }: {
  recordId: string;
  references: Reference[];
  records: RecordMeta[];        // record 셀렉트용 (자기 자신은 호출부에서 제외)
  onSaved: () => void;          // PUT 후 상세 재조회 (실패 시 롤백을 겸함)
  onOpenRecord: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<"paper" | "link" | "record">("paper");
  const [doi, setDoi] = useState("");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [refRecordId, setRefRecordId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function put(next: Reference[]) {
    setBusy(true);
    setError(null);
    try {
      await api.putReferences(recordId, next);
    } catch (e) {
      setError(`저장 실패 — ${(e as Error).message}`);
    } finally {
      setBusy(false);
      onSaved(); // 성공이든 실패든 서버 상태로 재동기화
    }
  }

  async function lookup() {
    const norm = normalizeDoi(doi);
    if (!norm) return;
    setBusy(true);
    setError(null);
    try {
      setTitle(await fetchDoiTitle(norm));
    } catch (e) {
      setError(`DOI 조회 실패 — 제목을 직접 입력하세요 (${(e as Error).message})`);
    } finally {
      setBusy(false);
    }
  }

  function add() {
    const ref: Reference =
      type === "record" ? { type, title: "", url: "", record_id: refRecordId }
      : type === "paper" ? { type, title: title.trim(), url: normalizeDoi(doi) ?? doi.trim(), record_id: "" }
      : { type, title: title.trim(), url: url.trim(), record_id: "" };
    if (type === "record" ? !ref.record_id : !(ref.title || ref.url)) return;
    void put([...references, ref]);
    setDoi(""); setUrl(""); setTitle(""); setRefRecordId("");
    setOpen(false);
  }

  function label(ref: Reference): string {
    if (ref.type !== "record") return ref.title || ref.url;
    const rec = records.find((r) => r.id === ref.record_id);
    return rec ? (rec.objective || rec.experiment_type || rec.id) : `${ref.record_id} (없는 레코드)`;
  }

  return (
    <div className="mt-4">
      <div className="font-semibold">참고문헌</div>
      <div className="mt-1 space-y-1">
        {references.map((ref, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <span>{ICON[ref.type] ?? "📎"}</span>
            {ref.type === "record" ? (
              <button onClick={() => ref.record_id && onOpenRecord(ref.record_id)}
                className="min-w-0 truncate text-left text-blue-600 hover:underline">{label(ref)}</button>
            ) : (
              <a href={ref.url} target="_blank" rel="noreferrer"
                className="min-w-0 truncate text-blue-600 hover:underline">{label(ref)}</a>
            )}
            <button onClick={() => void put(references.filter((_, j) => j !== i))} disabled={busy}
              aria-label="참조 삭제" className="ml-auto px-2 text-slate-400 hover:text-red-500">✕</button>
          </div>
        ))}
        {references.length === 0 && !open && <div className="text-sm text-slate-400">아직 없음</div>}
      </div>

      {!open && (
        <button onClick={() => setOpen(true)}
          className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
          ＋ 참고문헌 추가
        </button>
      )}
      {open && (
        <div className="mt-2 space-y-2 rounded-xl border border-slate-200 bg-white p-3">
          <div className="flex gap-2">
            {(Object.keys(TYPE_LABEL) as (keyof typeof TYPE_LABEL)[]).map((t) => (
              <button key={t} onClick={() => setType(t)}
                className={`rounded-full border px-3 py-1 text-sm ${type === t ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-300"}`}>
                {ICON[t]} {TYPE_LABEL[t]}
              </button>
            ))}
          </div>
          {type === "paper" && (
            <>
              <div className="flex flex-col gap-2 md:flex-row">
                <input value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="DOI (10.xxxx/... 또는 doi.org 링크)"
                  className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1.5 text-sm" />
                <button onClick={() => void lookup()} disabled={busy || !normalizeDoi(doi)}
                  className="rounded border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">조회</button>
              </div>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="제목 (조회로 자동 입력 또는 직접 입력)"
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm" />
            </>
          )}
          {type === "link" && (
            <>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="URL"
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm" />
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="설명 (선택)"
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm" />
            </>
          )}
          {type === "record" && (
            <select value={refRecordId} onChange={(e) => setRefRecordId(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm">
              <option value="">참조할 레코드 선택</option>
              {records.map((r) => (
                <option key={r.id} value={r.id}>{r.id} — {r.objective || r.experiment_type}</option>
              ))}
            </select>
          )}
          <div className="flex justify-end gap-2">
            <button onClick={() => { setOpen(false); setError(null); }}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">취소</button>
            <button onClick={add} disabled={busy}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-40">추가</button>
          </div>
        </div>
      )}
      {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Notes.tsx 통합**

import 추가:

```tsx
import ReferencesSection from "../components/ReferencesSection";
```

"원인 후보" 블록(`{detail.record.suspected_causes.length > 0 && (...)}`) 바로 아래에:

```tsx
              <ReferencesSection recordId={detail.record.id}
                references={detail.record.references ?? []}
                records={records.filter((r) => r.id !== detail.record.id)}
                onSaved={() => { api.getRecord(detail.record.id).then(setDetail).catch(() => {}); void loadList(); }}
                onOpenRecord={(rid) => nav(`/notes/${rid}`)} />
```

- [ ] **Step 3: ReferencesSection.test.tsx 작성**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReferencesSection from "./ReferencesSection";

describe("ReferencesSection", () => {
  it("참조 목록을 렌더하고 없는 레코드를 표시한다", () => {
    render(<ReferencesSection recordId="r1" records={[]}
      onSaved={() => {}} onOpenRecord={() => {}}
      references={[
        { type: "paper", title: "ALD 논문 (Kim, 2020)", url: "https://doi.org/10.1/x", record_id: "" },
        { type: "record", title: "", url: "", record_id: "삭제된것" },
      ]} />);
    expect(screen.getByText(/ALD 논문/)).toBeTruthy();
    expect(screen.getByText(/없는 레코드/)).toBeTruthy();
  });
});
```

- [ ] **Step 4: 체크 1회 (전체 테스트 + 빌드)**

Run: `cd web && npx vitest run && npm run build`
Expected: 전체 통과 (기존 12 + 신규 5 = 17) + 빌드 성공

- [ ] **Step 5: 커밋 + 푸시 (dist 포함)**

```bash
git add web/src web/dist
git commit -m "feat: 연구노트 참고문헌 섹션 — 목록·추가 폼·DOI 조회 연동"
git push origin frontend
```

---

## 백엔드 의존 메모

- Task 1~3 전부 백엔드 없이 빌드·테스트 통과한다 (`references ?? []` 가드).
- 실기기 수동 검증(추가→새로고침→유지)은 backend 세션이 PUT 엔드포인트를
  병합한 뒤에만 가능. main 머지는 그 시점에 함께 한다.

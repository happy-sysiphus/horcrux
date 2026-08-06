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

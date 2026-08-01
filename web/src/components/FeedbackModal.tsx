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

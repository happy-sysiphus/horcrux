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

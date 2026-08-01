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

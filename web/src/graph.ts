import type { RecordMeta } from "./types";

export type NodeKind = "exp" | "equipment" | "material" | "cause";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  full: string;       // cause는 원문 전체 — 상세 패널용
  recIds: string[];   // 연결된 실험 레코드 id (exp 노드는 자기 자신)
}
export interface GraphLink { source: string; target: string }

const CAUSE_LABEL_MAX = 30;
const EXP_LABEL_MAX = 24;

const truncate = (s: string, max: number) => (s.length > max ? s.slice(0, max) + "…" : s);

// GET /api/records 메타에서 노드·엣지 유도 — 서버 신규 계층 없이 클라이언트에서 완결.
// 동일성 판정은 trim 후 문자열 일치. 원인은 resolution.actual_cause(확정)만 노드로 올린다
// — suspected_causes는 목록 API에 없고, 자유 서술이라 미확정까지 합치면 노드가 안 겹친다.
export function buildGraph(records: RecordMeta[]): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes = new Map<string, GraphNode>();
  const linkKeys = new Set<string>();
  const links: GraphLink[] = [];
  const expIds = new Set(records.map((r) => r.id));

  const addLink = (source: string, target: string) => {
    const key = `${source}→${target}`;
    if (linkKeys.has(key)) return;
    linkKeys.add(key);
    links.push({ source, target });
  };
  const entity = (kind: NodeKind, name: string, recId: string): string | null => {
    const clean = name.trim();
    if (!clean) return null;
    const id = `${kind}:${clean}`;
    const existing = nodes.get(id);
    if (existing) {
      if (!existing.recIds.includes(recId)) existing.recIds.push(recId);
      return id;
    }
    const label = kind === "cause" ? truncate(clean, CAUSE_LABEL_MAX) : clean;
    nodes.set(id, { id, kind, label, full: clean, recIds: [recId] });
    return id;
  };

  // 라벨은 다른 화면과 동일하게 objective 우선 — experiment_type은 저카디널리티라
  // (같은 유형 반복 실험이 흔함) 라벨이 전부 겹친다. full=id는 호버 툴팁용(유일값).
  for (const r of records)
    nodes.set(r.id, {
      id: r.id, kind: "exp",
      label: truncate(r.objective || r.experiment_type || r.id, EXP_LABEL_MAX),
      full: r.id, recIds: [r.id],
    });

  for (const r of records) {
    for (const e of r.equipment) {
      const t = entity("equipment", e, r.id);
      if (t) addLink(r.id, t);
    }
    for (const m of r.materials) {
      const t = entity("material", m, r.id);
      if (t) addLink(r.id, t);
    }
    if (r.resolution.resolved && r.resolution.actual_cause?.trim()) {
      const t = entity("cause", r.resolution.actual_cause, r.id);
      if (t) addLink(r.id, t);
    }
    if (r.followup_of && expIds.has(r.followup_of)) addLink(r.followup_of, r.id);
  }
  return { nodes: [...nodes.values()], links };
}

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "../api";
import { buildGraph, type GraphNode, type NodeKind } from "../graph";
import RecordCard from "../components/RecordCard";
import type { RecordMeta } from "../types";

const KIND_LABEL: Record<NodeKind, string> = { exp: "실험", equipment: "장비", material: "재료", cause: "원인" };
const KIND_COLOR: Record<NodeKind, string> = { exp: "#3b82f6", equipment: "#10b981", material: "#8b5cf6", cause: "#f59e0b" };
const KIND_CHIP: Record<NodeKind, string> = {
  exp: "bg-blue-100 text-blue-700", equipment: "bg-emerald-100 text-emerald-700",
  material: "bg-violet-100 text-violet-700", cause: "bg-amber-100 text-amber-700",
};

export default function Graph() {
  const nav = useNavigate();
  const [records, setRecords] = useState<RecordMeta[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<ReadonlySet<NodeKind>>(new Set());
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 600, h: 400 });

  useEffect(() => {
    api.listRecords()
      .then((r) => setRecords(r.records))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoaded(true));
  }, []);

  // 캔버스는 컨테이너를 자동 추적하지 않는다 — 마운트 때 즉시 재고,
  // 이후 패널 열림/창 크기 변화는 ResizeObserver로 따라간다.
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // force-graph는 넘긴 객체에 좌표를 덧쓰며 링크의 source/target을 노드 참조로 바꾼다.
  // 재계산 때마다 새 사본을 만들어 원본(테스트 가능 순수 데이터)을 보호한다.
  const data = useMemo(() => {
    const { nodes, links } = buildGraph(records);
    const visible = nodes.filter((n) => !hidden.has(n.kind));
    const ids = new Set(visible.map((n) => n.id));
    return {
      nodes: visible.map((n) => ({ ...n })),
      links: links.filter((l) => ids.has(l.source) && ids.has(l.target)).map((l) => ({ ...l })),
    };
  }, [records, hidden]);

  const toggle = (k: NodeKind) => {
    const next = new Set(hidden);
    if (next.has(k)) next.delete(k); else next.add(k);
    setHidden(next);
    setSelected(null);
  };

  const related = selected ? records.filter((r) => selected.recIds.includes(r.id)) : [];
  const selectedRec = selected?.kind === "exp" ? records.find((r) => r.id === selected.id) : undefined;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">그래프뷰</div>
          <div className="text-xs text-slate-400">실험·장비·재료·원인의 관계를 탐색합니다</div>
        </header>
        <div ref={wrap} className="relative min-h-0 flex-1 bg-slate-50">
          <div className="absolute left-4 top-4 z-10 flex gap-2">
            {(Object.keys(KIND_LABEL) as NodeKind[]).map((k) => (
              <button key={k} onClick={() => toggle(k)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${hidden.has(k) ? "bg-slate-100 text-slate-400 line-through" : KIND_CHIP[k]}`}>
                {KIND_LABEL[k]}
              </button>
            ))}
          </div>
          {error && <div className="p-8 text-sm text-red-600">기록을 불러오지 못했습니다 — {error}</div>}
          {!error && loaded && records.length === 0 && (
            <div className="p-8 text-sm text-slate-500">저장된 기록이 없습니다. 실험을 기록하면 그래프가 만들어져요.</div>
          )}
          {!error && records.length > 0 && (
            <ForceGraph2D
              width={size.w} height={size.h}
              graphData={data}
              nodeCanvasObject={(node, ctx, scale) => {
                const n = node as unknown as GraphNode & { x: number; y: number };
                const r = n.kind === "exp" ? 6 : 4;
                ctx.fillStyle = KIND_COLOR[n.kind];
                ctx.beginPath();
                ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
                ctx.fill();
                if (selected?.id === n.id) {
                  ctx.strokeStyle = "#1e293b";
                  ctx.lineWidth = 1.5 / scale;
                  ctx.stroke();
                }
                ctx.font = `${11 / scale}px sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = "#475569";
                ctx.fillText(n.label, n.x, n.y + r + 2 / scale);
              }}
              nodePointerAreaPaint={(node, color, ctx) => {
                const n = node as unknown as { x: number; y: number };
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(n.x, n.y, 8, 0, 2 * Math.PI);
                ctx.fill();
              }}
              linkColor={() => "#cbd5e1"}
              onNodeClick={(node) => setSelected(node as unknown as GraphNode)}
              onBackgroundClick={() => setSelected(null)}
            />
          )}
        </div>
      </div>

      {selected && (
        <aside className="w-80 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-5">
          <div className="text-xs font-semibold text-slate-400">노드 상세</div>
          <span className={`mt-3 inline-block rounded-full px-2 py-0.5 text-xs ${KIND_CHIP[selected.kind]}`}>
            {KIND_LABEL[selected.kind]}
          </span>
          <div className="mt-2 break-words text-lg font-bold">
            {selected.kind === "cause" ? selected.full : selected.label}
          </div>

          {selectedRec ? (
            <div className="mt-4 space-y-3 text-sm">
              <div><span className="text-slate-400">날짜</span> {selectedRec.date}</div>
              {selectedRec.objective && <div><span className="text-slate-400">목적</span> {selectedRec.objective}</div>}
              {selectedRec.symptom.category !== "none" && (
                <div><span className="text-slate-400">증상</span> {selectedRec.symptom.description}</div>
              )}
              <button onClick={() => nav(`/notes/${selectedRec.id}`)}
                className="w-full rounded-lg bg-blue-600 py-2 text-sm text-white hover:bg-blue-700">
                기록 열기
              </button>
            </div>
          ) : (
            <div className="mt-4">
              <div className="flex gap-6 text-sm">
                <div><div className="text-slate-400">연결된 실험</div><div className="font-bold">{related.length}건</div></div>
                <div>
                  <div className="text-slate-400">확정 사례</div>
                  <div className="font-bold">{related.filter((r) => r.resolution.resolved).length}건</div>
                </div>
              </div>
              <div className="mt-4 text-xs font-semibold text-slate-400">관련 기록</div>
              <div className="mt-2 space-y-2">
                {related.map((r) => (
                  <RecordCard key={r.id} meta={r} onClick={() => nav(`/notes/${r.id}`)} />
                ))}
              </div>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}

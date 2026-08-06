import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import FeedbackModal from "../components/FeedbackModal";
import { resolutionLabel } from "../components/RecordCard";
import ReferencesSection from "../components/ReferencesSection";
import { MobileBar } from "../nav";
import { newSession, saveSession } from "../store";
import { symptomCategoryLabels } from "../types";
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
    // 모바일은 마스터-디테일: 목록과 상세를 라우트(:id)로 갈라 각각 전폭을 쓴다
    <div className="flex h-screen flex-col md:flex-row">
      <div className={`min-h-0 w-full flex-col border-slate-200 bg-white md:flex md:w-80 md:flex-none md:shrink-0 md:border-r
        ${id ? "hidden" : "flex flex-1"}`}>
        <MobileBar title="연구노트" />
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="hidden text-lg font-bold md:block">연구노트</div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="기록 검색 (장비·재료·증상...)"
            className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          <div className="mt-2 flex items-center gap-1 text-xs">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="min-w-0 flex-1 rounded border border-slate-200 px-2 py-1.5" />
            <span className="text-slate-400">~</span>
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="min-w-0 flex-1 rounded border border-slate-200 px-2 py-1.5" />
            {(from || to) && (
              <button onClick={() => { setFrom(""); setTo(""); }} className="px-1 text-slate-400 hover:text-slate-600">✕</button>
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
      </div>

      <div className={`min-h-0 min-w-0 flex-col md:flex md:flex-1 ${id ? "flex flex-1" : "hidden"}`}>
        {/* 상세에서는 햄버거 대신 목록으로 돌아가는 경로를 준다 */}
        <header className="flex shrink-0 items-center gap-2 border-b border-slate-200 bg-white px-3 py-2 md:hidden">
          <button onClick={() => nav("/notes")}
            className="rounded-lg bg-slate-100 px-3 py-2 text-sm">← 목록</button>
          <div className="min-w-0 truncate text-sm font-bold">{detail?.record.id ?? "기록"}</div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6 md:p-8">
          {!detail && <div className="text-slate-400">왼쪽에서 기록을 선택하세요.</div>}
          {detail && (
            <div className="mx-auto max-w-3xl">
              <div className="text-xs font-medium text-blue-600">{detail.record.id}</div>
              <h1 className="mt-1 text-xl font-bold md:text-2xl">{detail.record.objective || detail.record.experiment_type}</h1>
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
              <div className="mt-5 grid grid-cols-2 gap-3 rounded-xl bg-slate-100 p-4 text-sm md:grid-cols-4">
                <div><div className="text-xs text-slate-400">장비</div>{detail.record.equipment.join(", ") || "-"}</div>
                <div><div className="text-xs text-slate-400">재료</div>{detail.record.materials.join(", ") || "-"}</div>
                <div><div className="text-xs text-slate-400">증상</div>{symptomCategoryLabels[detail.record.symptom.category]}</div>
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
              <ReferencesSection recordId={detail.record.id}
                references={detail.record.references ?? []}
                records={records.filter((r) => r.id !== detail.record.id)}
                onSaved={() => { api.getRecord(detail.record.id).then(setDetail).catch(() => {}); void loadList(); }}
                onOpenRecord={(rid) => nav(`/notes/${rid}`)} />
              <div className="mt-4">
                <div className="font-semibold">본문</div>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-xl bg-white p-4 text-sm shadow-sm">{detail.body}</pre>
              </div>
              <div className="mt-6 flex flex-col gap-3 md:flex-row">
                <button onClick={() => setModal(true)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm hover:bg-slate-50">
                  실험 피드백
                </button>
                <button onClick={startFollowup}
                  className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm text-white hover:bg-blue-700">
                  후속 실험 기록
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      {modal && detail && (
        <FeedbackModal detail={detail} onClose={() => setModal(false)}
          onDone={() => { setModal(false); api.getRecord(detail.record.id).then(setDetail); void loadList(); }} />
      )}
    </div>
  );
}

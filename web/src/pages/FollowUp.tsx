import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import DiffPanel from "../components/DiffPanel";
import { resolutionLabel } from "../components/RecordCard";
import StructurePanel, { gaugeGaps } from "../components/StructurePanel";
import { MobileBar, MobileTabs } from "../nav";
import { useLogLoop } from "../useLogLoop";
import type { RecordDetail } from "../types";

export default function FollowUp() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse, rewind, fork } = useLogLoop(sid);
  const [base, setBase] = useState<RecordDetail | null>(null);
  const [tab, setTab] = useState<"base" | "chat" | "panel">("chat");

  useEffect(() => {
    if (session?.baseId) api.getRecord(session.baseId).then(setBase).catch(() => {});
  }, [session?.baseId]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  const done = Math.max(requiredTotal - gaugeGaps(session.gaps).length, 0);

  return (
    <div className="flex h-screen flex-col md:flex-row">
      {/* 모바일 전용 바·탭 — 데스크톱은 3단이 동시에 보이므로 불필요 */}
      <div className="shrink-0 md:hidden">
        <MobileBar title={session.title} subtitle={`${session.baseId}에서 이어짐`} />
        <MobileTabs value={tab} onChange={setTab} tabs={[
          { key: "base", label: "기준 실험" },
          { key: "chat", label: "대화" },
          { key: "panel", label: <>구조 · {done}/{requiredTotal}{session.gaps.length > 0 && " ⚠"}</> },
        ]} />
      </div>

      <div className={`min-h-0 w-full overflow-y-auto border-slate-200 bg-white p-5 md:w-72 md:shrink-0 md:border-r
        ${tab === "base" ? "flex-1" : "hidden md:block"}`}>
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

      <div className={`min-w-0 flex-col md:flex md:min-h-0 md:flex-1 ${tab === "chat" ? "flex min-h-0 flex-1" : "hidden"}`}>
        <header className="hidden border-b border-slate-200 bg-white px-6 py-3 md:block">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">{session.baseId}에서 이어짐</div>
        </header>
        {error && (
          <div className="flex flex-wrap gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} onSend={onSend} busy={busy}
            placeholder="후속 실험 내용을 입력하세요 (무엇을 바꿨고 결과가 어땠는지)"
            onRewind={session.saved ? undefined : rewind}
            onFork={session.saved ? undefined : fork} />
        </div>
      </div>

      <StructurePanel parsed={session.parsed} gaps={session.gaps} canSave={canSave}
        requiredTotal={requiredTotal} saveLabel="검토 후 저장"
        className={tab === "panel" ? "flex" : "hidden md:flex"}
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}

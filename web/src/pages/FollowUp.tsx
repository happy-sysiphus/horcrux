import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import DiffPanel from "../components/DiffPanel";
import { resolutionLabel } from "../components/RecordCard";
import StructurePanel from "../components/StructurePanel";
import { useLogLoop } from "../useLogLoop";
import type { RecordDetail } from "../types";

export default function FollowUp() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse, rewind, fork } = useLogLoop(sid);
  const [base, setBase] = useState<RecordDetail | null>(null);

  useEffect(() => {
    if (session?.baseId) api.getRecord(session.baseId).then(setBase).catch(() => {});
  }, [session?.baseId]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  return (
    <div className="flex h-screen">
      <div className="w-72 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-5">
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
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">{session.baseId}에서 이어짐</div>
        </header>
        {error && (
          <div className="flex gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
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
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}

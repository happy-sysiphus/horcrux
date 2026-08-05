import { useNavigate, useParams } from "react-router-dom";
import ChatPane from "../components/ChatPane";
import StructurePanel from "../components/StructurePanel";
import { useLogLoop } from "../useLogLoop";

export default function LogChat() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse, rewind, fork } = useLogLoop(sid);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">연구 기록</div>
        </header>
        {error && (
          <div className="flex items-center gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장 (needs_review)</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} onSend={onSend} busy={busy}
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

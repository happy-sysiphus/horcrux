import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ChatPane from "../components/ChatPane";
import StructurePanel, { gaugeGaps } from "../components/StructurePanel";
import { MobileBar, MobileTabs } from "../nav";
import { useLogLoop } from "../useLogLoop";

export default function LogChat() {
  const { sid } = useParams();
  const nav = useNavigate();
  const { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse, rewind, fork } = useLogLoop(sid);
  const [tab, setTab] = useState<"chat" | "panel">("chat");

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  const done = Math.max(requiredTotal - gaugeGaps(session.gaps).length, 0);

  return (
    <div className="flex h-screen flex-col md:flex-row">
      {/* 모바일에서 '구조' 탭이면 이 열은 바·탭만 차지하고 남는 높이를 패널에 넘긴다 */}
      <div className={`flex min-w-0 flex-col md:min-h-0 md:flex-1 ${tab === "chat" ? "min-h-0 flex-1" : "shrink-0"}`}>
        <MobileBar title={session.title} subtitle="연구 기록" />
        <header className="hidden border-b border-slate-200 bg-white px-6 py-3 md:block">
          <div className="font-bold">{session.title}</div>
          <div className="text-xs text-slate-400">연구 기록</div>
        </header>
        <MobileTabs value={tab} onChange={setTab} tabs={[
          { key: "chat", label: "대화" },
          { key: "panel", label: <>구조 · {done}/{requiredTotal}{session.gaps.length > 0 && " ⚠"}</> },
        ]} />
        {error && (
          <div className="flex flex-wrap items-center gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runParse(session)} className="underline">재시도</button>
            <button onClick={onSaveRaw} className="underline">원문만 저장 (needs_review)</button>
          </div>
        )}
        <div className={`min-h-0 flex-1 ${tab === "chat" ? "" : "hidden md:block"}`}>
          <ChatPane messages={session.messages} onSend={onSend} busy={busy}
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

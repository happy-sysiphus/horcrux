import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import RecordCard from "../components/RecordCard";
import { getSession, saveSession } from "../store";
import type { Session } from "../types";

// 근거 3단 라벨 (스펙 ③) — records 단도 표시해야 3단이 성립
const BANNERS = {
  none: { text: "⚠ 축적된 유사 사례가 없어 일반 지식 기반 조언입니다.", cls: "bg-red-50 text-red-700" },
  wiki: { text: "ℹ 유사 레코드는 없어 연구실 위키 아티클 기반 안내입니다.", cls: "bg-blue-50 text-blue-700" },
  records: { text: "✓ 연구실 실험 기록을 근거로 한 답변입니다.", cls: "bg-emerald-50 text-emerald-700" },
} as const;

export default function Ask() {
  const { sid } = useParams();
  const nav = useNavigate();
  const [session, setSession] = useState<Session | null>(() => getSession(sid ?? "") ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  function update(s: Session) {
    saveSession(s);
    setSession({ ...s });
  }

  async function runAsk(s: Session, text: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.ask(text);
      s.askResult = result;
      s.title = text.slice(0, 30);
      s.messages.push({ role: "ai", text: result.answer });
      update(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    if (session.rawText && session.messages.length === 0) {
      session.messages.push({ role: "user", text: session.rawText });
      void runAsk(session, session.rawText);
    }
  }, [session]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;
  const banner = session.askResult ? BANNERS[session.askResult.evidence] : null;

  return (
    <div className="flex h-screen">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <div className="font-bold">{session.title === "새 대화" ? "과거 기록 분석" : session.title}</div>
          <div className="text-xs text-slate-400">과거 기록 분석</div>
        </header>
        {banner && <div className={`px-6 py-2 text-sm ${banner.cls}`}>{banner.text}</div>}
        {error && (
          <div className="flex gap-3 bg-red-50 px-6 py-2 text-sm text-red-700">
            {error}
            <button onClick={() => runAsk(session, session.rawText)} className="underline">재시도</button>
          </div>
        )}
        <div className="min-h-0 flex-1">
          <ChatPane messages={session.messages} busy={busy}
            placeholder="추가 질문을 입력하세요"
            onSend={(t) => {
              session.messages.push({ role: "user", text: t });
              session.rawText = t;
              update(session);
              void runAsk(session, t);
            }} />
        </div>
      </div>
      <div className="w-80 shrink-0 overflow-y-auto border-l border-slate-200 bg-white p-5">
        <div className="text-lg font-bold">유사 사례</div>
        {!session.askResult && <div className="mt-4 text-sm text-slate-400">질문하면 관련 기록이 표시됩니다.</div>}
        <div className="mt-3 space-y-3">
          {session.askResult?.records.map((r) => (
            <RecordCard key={r.id} meta={r} onClick={() => nav(`/notes/${r.id}`)} />
          ))}
          {session.askResult && session.askResult.records.length === 0 && (
            <div className="text-sm text-slate-400">관련 레코드 없음</div>
          )}
        </div>
        {session.askResult && session.askResult.wiki.length > 0 && (
          <div className="mt-5">
            <div className="text-xs text-slate-400">참고한 위키</div>
            {session.askResult.wiki.map((w) => (
              <div key={w} className="mt-1 rounded bg-slate-50 px-2 py-1 text-sm">{w}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

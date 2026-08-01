import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions, newSession, saveSession } from "../store";

export default function Home() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"log" | "ask">("log");
  const [text, setText] = useState("");
  const drafts = listSessions().filter((s) => s.kind !== "ask" && !s.saved && s.messages.length > 0);

  function start(kind: "log" | "ask", preset?: string) {
    const t = (preset ?? text).trim();
    if (!t) return;
    const s = newSession(kind);
    s.rawText = t;
    s.title = t.slice(0, 30);
    saveSession(s);
    nav(kind === "log" ? `/log/${s.id}` : `/ask/${s.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="text-3xl font-bold">무엇을 도와드릴까요?</h1>
      <p className="mt-2 text-slate-500">실험 기록, 문제 원인, 과거 사례를 자연어로 입력하면 AI가 정리합니다.</p>

      <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm w-fit">
          {(["log", "ask"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`rounded-md px-4 py-1.5 ${mode === m ? "bg-white font-medium shadow" : "text-slate-500"}`}>
              {m === "log" ? "실험 기록" : "문제 질문"}
            </button>
          ))}
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
          placeholder={mode === "log" ? "실험 내용을 자유롭게 입력하세요." : "문제 상황을 설명해주세요. 장비·재료·증상을 포함하면 더 정확합니다."}
          className="w-full resize-none outline-none placeholder:text-slate-400" />
        <div className="flex justify-end">
          <button onClick={() => start(mode)} disabled={!text.trim()}
            className="rounded-full bg-blue-600 px-5 py-2 text-sm text-white disabled:opacity-40">
            전송 ➤
          </button>
        </div>
      </div>

      <div className="mt-10">
        <h2 className="mb-3 font-semibold">빠른 시작</h2>
        <div className="grid grid-cols-2 gap-4">
          <button onClick={() => setMode("log")}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm hover:border-blue-400 ${mode === "log" ? "border-blue-400" : "border-slate-200"}`}>
            <div className="font-medium">📄 오늘 실험을 기록할게요</div>
            <div className="mt-1 text-sm text-slate-500">실험 조건과 결과를 구조화합니다.</div>
          </button>
          <button onClick={() => setMode("ask")}
            className={`rounded-xl border bg-white p-5 text-left shadow-sm hover:border-blue-400 ${mode === "ask" ? "border-blue-400" : "border-slate-200"}`}>
            <div className="font-medium">🔍 과거 유사 사례를 찾아주세요</div>
            <div className="mt-1 text-sm text-slate-500">연구실 기록에서 근거를 검색합니다.</div>
          </button>
        </div>
      </div>

      {drafts.length > 0 && (
        <div className="mt-10 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="font-medium">최근 미완료 기록 {drafts.length}건</div>
          <div className="text-sm text-slate-500">누락 정보를 이어서 입력하고 저장할 수 있어요.</div>
          <div className="mt-3 space-y-2">
            {drafts.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{d.title}</div>
                  <div className="text-xs text-slate-400">
                    {new Date(d.createdAt).toLocaleString("ko-KR")}
                    {d.kind === "followup" && " · 후속 실험"}
                  </div>
                </div>
                <button onClick={() => nav(d.kind === "followup" ? `/followup/${d.id}` : `/log/${d.id}`)}
                  className="shrink-0 rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
                  이어 작성
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

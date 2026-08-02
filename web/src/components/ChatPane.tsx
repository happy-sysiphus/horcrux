import { useEffect, useRef, useState } from "react";
import type { ChatMsg } from "../types";

export default function ChatPane({ messages, onSend, busy, placeholder }: {
  messages: ChatMsg[];
  onSend: (text: string) => void;
  busy: boolean;
  placeholder?: string;
}) {
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  // 블록 본문 필수 — 간결 본문이면 scrollIntoView의 반환값이 그대로 effect 반환값이 되고,
  // React가 그것을 정리 함수로 보고 호출한다. 확장/폴리필이 이 API를 덮어써 값을 돌려주면
  // 다음 렌더나 언마운트에서 "is not a function"으로 트리 전체가 죽는다.
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, busy]);

  function send(t: string) {
    if (!t.trim() || busy) return;
    setText("");
    onSend(t.trim());
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.map((m, i) => (
          <div key={i}>
            <div className={`text-xs text-slate-400 ${m.role === "user" ? "text-right" : ""}`}>
              {m.role === "user" ? "사용자" : "LAB GENE AI"}
            </div>
            <div className={m.role === "user"
              ? "ml-auto w-fit max-w-[80%] rounded-xl bg-blue-50 px-4 py-3 text-sm whitespace-pre-wrap"
              : "w-fit max-w-[85%] rounded-xl border-l-4 border-blue-500 bg-white px-4 py-3 text-sm shadow-sm whitespace-pre-wrap"}>
              {m.text}
            </div>
            {m.role === "ai" && m.chips && i === messages.length - 1 && !busy && (
              <div className="mt-2 flex flex-wrap gap-2">
                {m.chips.map((c) => (
                  <button key={c} onClick={() => send(c)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1 text-sm hover:border-blue-400 hover:text-blue-600">
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="text-sm text-slate-400 animate-pulse">분석 중... (수십 초 걸릴 수 있어요)</div>}
        <div ref={bottom} />
      </div>
      <div className="border-t border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2">
          <input value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(text)}
            placeholder={placeholder ?? "메시지를 입력하세요"} disabled={busy}
            className="flex-1 text-sm outline-none disabled:bg-transparent" />
          <button onClick={() => send(text)} disabled={busy || !text.trim()}
            className="rounded-full bg-blue-600 px-4 py-1.5 text-sm text-white disabled:opacity-40">➤</button>
        </div>
      </div>
    </div>
  );
}

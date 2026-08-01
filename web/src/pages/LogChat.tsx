import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import ChatPane from "../components/ChatPane";
import StructurePanel from "../components/StructurePanel";
import { getSession, saveSession } from "../store";
import type { Session } from "../types";

const MAX_ROUNDS = 3;

function chipsFor(gap: string): string[] {
  const chips = ["건너뛰기"];
  if (gap.includes("증상")) chips.unshift("문제 없음");
  return chips;
}

export default function LogChat() {
  const { sid } = useParams();
  const nav = useNavigate();
  const [session, setSession] = useState<Session | null>(() => getSession(sid ?? "") ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requiredTotal, setRequiredTotal] = useState(5);
  const started = useRef(false);

  useEffect(() => {
    api.config().then((c) =>
      setRequiredTotal(c.required_fields.length + c.required_parameters.length));
  }, []);

  function update(s: Session) {
    saveSession(s);
    setSession({ ...s });
  }

  async function runParse(s: Session) {
    setBusy(true);
    setError(null);
    try {
      const { parsed, gaps } = await api.parse(s.rawText);
      s.parsed = parsed;
      s.gaps = gaps;
      s.gapIndex = 0;
      s.answers = [];
      if (parsed.experiment_type || parsed.objective)
        s.title = parsed.experiment_type || parsed.objective.slice(0, 30);
      if (gaps.length > 0 && s.rounds < MAX_ROUNDS) {
        s.messages.push({ role: "ai", text: gaps[0], chips: chipsFor(gaps[0]) });
      } else if (gaps.length === 0) {
        s.messages.push({ role: "ai", text: "필요한 정보가 모두 채워졌습니다. 우측에서 검토 후 저장하세요." });
      } else {
        s.messages.push({ role: "ai", text: `아직 ${gaps.length}개 항목이 비어 있지만 재질문을 마칩니다. 우측에서 검토 후 저장하세요.` });
      }
      update(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // 홈에서 rawText만 담겨 넘어온 세션 자동 시작 (Task 4 규약)
  useEffect(() => {
    if (!session || started.current) return;
    started.current = true;
    if (session.rawText && session.messages.length === 0) {
      session.messages.push({ role: "user", text: session.rawText });
      void runParse(session);
    }
  }, [session]);

  if (!session) return <div className="p-8 text-slate-500">세션을 찾을 수 없습니다.</div>;

  async function onSend(text: string) {
    const s = session!;
    s.messages.push({ role: "user", text });
    if (!s.parsed) {
      // 첫 파싱 실패 후 재시도 케이스: 원문에 이어붙여 재파싱
      s.rawText = s.rawText ? `${s.rawText}\n${text}` : text;
      update(s);
      await runParse(s);
      return;
    }
    // gap 답변 수집 (재파싱 없음)
    if (text !== "건너뛰기") s.answers.push(text);
    s.gapIndex += 1;
    if (s.gapIndex < s.gaps.length) {
      const g = s.gaps[s.gapIndex];
      s.messages.push({ role: "ai", text: g, chips: chipsFor(g) });
      update(s);
      return;
    }
    // 마지막 gap 소진 → 필요 시 재파싱 1회
    if (s.answers.length === 0) {
      // gaps는 지우지 않는다 — 게이지는 마지막 파싱 결과를 정직하게 유지, 저장은 canSave가 허용
      s.messages.push({ role: "ai", text: "확인했습니다. 누락된 항목은 비운 채로 저장됩니다. 우측에서 검토하세요." });
      update(s);
      return;
    }
    s.rawText += `\n\n[추가 답변]\n${s.answers.join("\n")}`;
    s.rounds += 1;
    update(s);
    await runParse(s);
  }

  async function onSaveRaw() {
    const s = session!;
    const { id } = await api.saveRaw(s.rawText);
    s.saved = true;
    update(s);
    nav(`/notes/${id}`);
  }

  // 질문 루프를 끝냈거나 재질문 라운드를 소진해야 저장 진입 (스펙 ②)
  const canSave = session.gapIndex >= session.gaps.length || session.rounds >= MAX_ROUNDS;

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
          <ChatPane messages={session.messages} onSend={onSend} busy={busy} />
        </div>
      </div>
      <StructurePanel parsed={session.parsed} gaps={session.gaps} canSave={canSave}
        requiredTotal={requiredTotal} saveLabel="검토 후 저장"
        onSaveClick={() => nav(`/preview/${session.id}`)} />
    </div>
  );
}

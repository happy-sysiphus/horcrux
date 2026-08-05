import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { getSession, newSession, saveSession } from "./store";
import type { ConvoSnapshot, Session } from "./types";

const MAX_ROUNDS = 3;

function chipsFor(gap: string): string[] {
  const chips = ["건너뛰기"];
  if (gap.includes("증상")) chips.unshift("문제 없음");
  return chips;
}

export function useLogLoop(sid: string | undefined) {
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
        s.title = (s.kind === "followup" ? "후속: " : "") +
          (parsed.experiment_type || parsed.objective.slice(0, 30));
      if (gaps.length > 0 && s.rounds < MAX_ROUNDS) {
        s.messages.push({ role: "ai", text: gaps[0], chips: chipsFor(gaps[0]) });
      } else if (gaps.length === 0) {
        s.messages.push({ role: "ai", text: "필요한 정보가 모두 채워졌습니다. 검토 후 저장하세요." });
      } else {
        s.messages.push({ role: "ai", text: `아직 ${gaps.length}개 항목이 비어 있지만 재질문을 마칩니다. 검토 후 저장하세요.` });
      }
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
      void runParse(session);
    }
  }, [session]);

  function snapshot(s: Session): ConvoSnapshot {
    return structuredClone({
      rawText: s.rawText, messages: s.messages, parsed: s.parsed,
      gaps: s.gaps, gapIndex: s.gapIndex, answers: s.answers, rounds: s.rounds,
    });
  }

  // uIdx = 대화 내 사용자 발화 순번(0=초기 로그). history[uIdx-1]이 그 발화 직전 상태.
  function rewind(uIdx: number) {
    const s = session!;
    const snap = (s.history ?? [])[uIdx - 1];
    if (!snap || busy) return;
    Object.assign(s, structuredClone(snap));
    s.history = (s.history ?? []).slice(0, uIdx - 1);
    setError(null);
    update(s);
  }

  function fork(uIdx: number) {
    const s = session!;
    const snap = (s.history ?? [])[uIdx - 1];
    if (!snap || busy) return;
    const ns = newSession(s.kind, s.baseId);
    Object.assign(ns, structuredClone(snap));
    ns.title = "⑂ " + s.title;
    ns.history = [];
    saveSession(ns);
    nav(s.kind === "followup" ? `/followup/${ns.id}` : `/log/${ns.id}`);
  }

  async function onSend(text: string) {
    const s = session!;
    s.history = [...(s.history ?? []), snapshot(s)];
    s.messages.push({ role: "user", text });
    if (!s.parsed) {
      s.rawText = s.rawText ? `${s.rawText}\n${text}` : text;
      update(s);
      await runParse(s);
      return;
    }
    if (text !== "건너뛰기") s.answers.push(text);
    s.gapIndex += 1;
    if (s.gapIndex < s.gaps.length) {
      const g = s.gaps[s.gapIndex];
      s.messages.push({ role: "ai", text: g, chips: chipsFor(g) });
      update(s);
      return;
    }
    if (s.answers.length === 0) {
      // gaps는 지우지 않는다 — 게이지 정직성 유지, 저장 허용은 canSave가 판단
      s.messages.push({ role: "ai", text: "확인했습니다. 누락된 항목은 비운 채로 저장됩니다." });
      update(s);
      return;
    }
    s.rawText += `\n\n[추가 답변]\n${s.answers.join("\n")}`;
    s.rounds += 1;
    update(s);
    await runParse(s);
  }

  // 데이터 유실 방지 최후 경로 — 실패를 조용히 삼키면 사용자는 저장된 줄 안다
  async function onSaveRaw() {
    const s = session!;
    try {
      const { id } = await api.saveRaw(s.rawText);
      s.saved = true;
      update(s);
      nav(`/notes/${id}`);
    } catch (e) {
      setError(`원문 저장 실패 — ${(e as Error).message}`);
    }
  }

  // 질문 루프를 끝냈거나 재질문 라운드를 소진해야 저장 진입 (스펙 ②)
  const canSave = !!session &&
    (session.gapIndex >= session.gaps.length || session.rounds >= MAX_ROUNDS);

  return { session, busy, error, requiredTotal, canSave, onSend, onSaveRaw, runParse, rewind, fork };
}

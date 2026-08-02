import type { Session } from "./types";

const KEY = "labgene.sessions.v1";

// 이전 빌드가 저장한 구버전 세션(필드 누락)이 렌더를 터뜨리지 않도록 기본값 보정.
function normalize(s: Partial<Session>): Session {
  return {
    id: s.id ?? `${Date.now()}`, kind: s.kind ?? "log", title: s.title ?? "새 대화",
    createdAt: s.createdAt ?? 0, saved: s.saved ?? false, baseId: s.baseId,
    rawText: s.rawText ?? "", messages: Array.isArray(s.messages) ? s.messages : [],
    parsed: s.parsed ?? null, gaps: Array.isArray(s.gaps) ? s.gaps : [],
    gapIndex: s.gapIndex ?? 0, answers: Array.isArray(s.answers) ? s.answers : [],
    rounds: s.rounds ?? 0, askResult: s.askResult,
  };
}
function readAll(): Session[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((s) => s && typeof s === "object").map(normalize) : [];
  } catch {
    return [];
  }
}
function writeAll(list: Session[]) {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function listSessions(): Session[] {
  return readAll().sort((a, b) => b.createdAt - a.createdAt);
}
export function getSession(id: string): Session | undefined {
  return readAll().find((s) => s.id === id);
}
export function saveSession(s: Session) {
  const list = readAll().filter((x) => x.id !== s.id);
  list.push(s);
  writeAll(list);
}
export function deleteSession(id: string) {
  writeAll(readAll().filter((s) => s.id !== id));
}
export function newSession(kind: Session["kind"], baseId?: string): Session {
  const s: Session = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    kind, title: "새 대화", createdAt: Date.now(), saved: false, baseId,
    rawText: "", messages: [], parsed: null, gaps: [], gapIndex: 0,
    answers: [], rounds: 0,
  };
  saveSession(s);
  return s;
}

import type { Session } from "./types";

const KEY = "labgene.sessions.v1";

function readAll(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as Session[];
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

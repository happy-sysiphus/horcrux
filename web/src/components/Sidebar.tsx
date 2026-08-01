import { Link, useLocation, useNavigate } from "react-router-dom";
import { listSessions } from "../store";
import type { Session } from "../types";

function sessionPath(s: Session): string {
  if (s.kind === "ask") return `/ask/${s.id}`;
  if (s.kind === "followup") return `/followup/${s.id}`;
  return `/log/${s.id}`;
}

export default function Sidebar() {
  const nav = useNavigate();
  const loc = useLocation();
  const sessions = listSessions();
  const today = new Date().toDateString();
  const isToday = (s: Session) => new Date(s.createdAt).toDateString() === today;
  const group = (list: Session[], label: string) =>
    list.length > 0 && (
      <div className="mt-4">
        <div className="px-3 text-xs text-slate-400">{label}</div>
        {list.map((s) => (
          <Link key={s.id} to={sessionPath(s)}
            className={`block truncate rounded px-3 py-2 text-sm hover:bg-slate-100 ${
              loc.pathname.includes(s.id) ? "bg-blue-50 text-blue-700" : "text-slate-700"}`}>
            {s.title}
          </Link>
        ))}
      </div>
    );

  return (
    <div className="flex h-screen">
      <nav className="flex w-52 shrink-0 flex-col bg-slate-900 p-4 text-slate-200">
        <div className="mb-8 flex items-center gap-2 font-bold tracking-wide">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600">⚗</span>
          LAB GENE
        </div>
        <Link to="/" className={`rounded px-3 py-2 text-sm ${loc.pathname === "/" ? "bg-slate-700" : "hover:bg-slate-800"}`}>
          ✦ AI 워크스페이스
        </Link>
        <Link to="/notes" className={`mt-1 rounded px-3 py-2 text-sm ${loc.pathname.startsWith("/notes") ? "bg-slate-700" : "hover:bg-slate-800"}`}>
          ▤ 연구노트
        </Link>
      </nav>
      <aside className="w-60 shrink-0 overflow-y-auto border-r border-slate-200 bg-white p-3">
        <button onClick={() => nav("/")}
          className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700">
          + 새 대화
        </button>
        {group(sessions.filter(isToday), "오늘")}
        {group(sessions.filter((s) => !isToday(s)), "이전")}
      </aside>
    </div>
  );
}

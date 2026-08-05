import { Link, useLocation, useNavigate } from "react-router-dom";
import { useNav } from "../nav";
import { listSessions } from "../store";
import type { Session } from "../types";

function sessionPath(s: Session): string {
  if (s.kind === "ask") return `/ask/${s.id}`;
  if (s.kind === "followup") return `/followup/${s.id}`;
  return `/log/${s.id}`;
}

const LINKS = [
  { to: "/", icon: "✦", label: "AI 워크스페이스", match: (p: string) => p === "/" },
  { to: "/notes", icon: "▤", label: "연구노트", match: (p: string) => p.startsWith("/notes") },
  { to: "/graph", icon: "◈", label: "그래프뷰", match: (p: string) => p.startsWith("/graph") },
];

export default function Sidebar() {
  const nav = useNavigate();
  const loc = useLocation();
  const { open, setOpen } = useNav();
  const close = () => setOpen(false);
  const sessions = listSessions();
  const today = new Date().toDateString();
  const isToday = (s: Session) => new Date(s.createdAt).toDateString() === today;

  const navLinks = (dark: boolean) =>
    LINKS.map((l) => (
      <Link key={l.to} to={l.to} onClick={close}
        className={`rounded px-3 py-2 text-sm ${dark
          ? (l.match(loc.pathname) ? "bg-slate-700" : "hover:bg-slate-800")
          : (l.match(loc.pathname) ? "bg-blue-50 font-medium text-blue-700" : "text-slate-700 hover:bg-slate-100")}`}>
        {l.icon} {l.label}
      </Link>
    ));

  const group = (list: Session[], label: string) =>
    list.length > 0 && (
      <div className="mt-4">
        <div className="px-3 text-xs text-slate-400">{label}</div>
        {list.map((s) => (
          <Link key={s.id} to={sessionPath(s)} onClick={close}
            className={`block truncate rounded px-3 py-2 text-sm ${
              loc.pathname.includes(s.id) ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-100"}`}>
            {s.title}
          </Link>
        ))}
      </div>
    );

  return (
    <>
      {open && (
        <div onClick={close} aria-hidden
          className="fixed inset-0 z-30 bg-slate-900/45 md:hidden" />
      )}
      {/* 모바일: 좌측 오버레이 드로어 / 데스크톱: 다크 레일 + 세션 목록 2단 고정.
          닫힘은 translate가 아니라 hidden — 화면 밖 요소가 남지 않아 터치·탭 순서도 깨끗하다. */}
      <div className={`fixed inset-y-0 left-0 z-40 w-4/5 max-w-xs shadow-2xl
        md:static md:z-auto md:flex md:h-screen md:w-auto md:max-w-none md:shadow-none
        ${open ? "flex" : "hidden"}`}>
        <nav className="hidden w-52 shrink-0 flex-col gap-1 bg-slate-900 p-4 text-slate-200 md:flex">
          <div className="mb-8 flex items-center gap-2 font-bold tracking-wide">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600">⚗</span>
            LAB GENE
          </div>
          {navLinks(true)}
        </nav>

        <aside className="flex min-w-0 flex-1 flex-col bg-white md:w-60 md:flex-none md:border-r md:border-slate-200">
          <div className="flex items-center gap-2 bg-slate-900 px-4 py-3 font-bold tracking-wide text-white md:hidden">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-sm">⚗</span>
            LAB GENE
          </div>
          <div className="p-3">
            <button onClick={() => { close(); nav("/"); }}
              className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700">
              + 새 대화
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
            {group(sessions.filter(isToday), "오늘")}
            {group(sessions.filter((s) => !isToday(s)), "이전")}
          </div>
          <div className="flex flex-col gap-1 border-t border-slate-200 p-3 md:hidden">
            {navLinks(false)}
          </div>
        </aside>
      </div>
    </>
  );
}

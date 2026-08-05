import { createContext, useContext, useState, type ReactNode } from "react";

// 모바일 드로어 개폐 상태 — 사이드바(App)와 각 페이지의 햄버거 버튼이 공유한다.
const NavCtx = createContext<{ open: boolean; setOpen: (v: boolean) => void }>({
  open: false, setOpen: () => {},
});
export const useNav = () => useContext(NavCtx);

export function NavProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <NavCtx.Provider value={{ open, setOpen }}>{children}</NavCtx.Provider>;
}

// md 미만에서만 보이는 상단 바. 데스크톱은 각 페이지의 기존 header가 대신한다.
export function MobileBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { setOpen } = useNav();
  return (
    <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-3 py-2 md:hidden">
      <button onClick={() => setOpen(true)} aria-label="메뉴 열기"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-lg">
        ☰
      </button>
      <div className="min-w-0">
        <div className="truncate font-bold">{title}</div>
        {subtitle && <div className="truncate text-xs text-slate-400">{subtitle}</div>}
      </div>
    </header>
  );
}

// 데스크톱의 다단 레이아웃을 모바일에서 갈라 보여주는 탭
export function MobileTabs<T extends string>({ tabs, value, onChange }: {
  tabs: { key: T; label: ReactNode }[];
  value: T;
  onChange: (k: T) => void;
}) {
  return (
    <div className="flex shrink-0 border-b border-slate-200 bg-white text-sm md:hidden">
      {tabs.map((t) => (
        <button key={t.key} onClick={() => onChange(t.key)}
          className={`flex-1 py-2.5 ${value === t.key
            ? "font-semibold text-blue-600 shadow-[inset_0_-2px_0_var(--color-blue-600)]"
            : "text-slate-500"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

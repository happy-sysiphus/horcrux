import { Fragment, type ReactNode } from "react";
import { HashRouter, Route, Routes, useParams } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import { NavProvider } from "./nav";
import Ask from "./pages/Ask";
import FollowUp from "./pages/FollowUp";
import Graph from "./pages/Graph";
import Home from "./pages/Home";
import LogChat from "./pages/LogChat";
import Notes from "./pages/Notes";
import Preview from "./pages/Preview";

// 같은 route 안에서 :sid만 바뀌면 React가 컴포넌트를 remount하지 않아 훅 내부 세션 상태와
// 자동 시작 가드가 이전 세션에 남는다. key로 세션마다 강제 remount.
function BySid({ children }: { children: ReactNode }) {
  const { sid } = useParams();
  return <Fragment key={sid}>{children}</Fragment>;
}

export default function App() {
  return (
    <HashRouter>
      <NavProvider>
      <div className="flex h-screen bg-slate-50 text-slate-900">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/log/:sid" element={<BySid><LogChat /></BySid>} />
            <Route path="/ask/:sid" element={<BySid><Ask /></BySid>} />
            <Route path="/preview/:sid" element={<Preview />} />
            <Route path="/graph" element={<Graph />} />
            <Route path="/notes" element={<Notes />} />
            <Route path="/notes/:id" element={<Notes />} />
            <Route path="/followup/:sid" element={<BySid><FollowUp /></BySid>} />
          </Routes>
        </main>
      </div>
      </NavProvider>
    </HashRouter>
  );
}

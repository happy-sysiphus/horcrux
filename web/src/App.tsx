import { HashRouter, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Ask from "./pages/Ask";
import FollowUp from "./pages/FollowUp";
import Home from "./pages/Home";
import LogChat from "./pages/LogChat";
import Notes from "./pages/Notes";
import Preview from "./pages/Preview";

export default function App() {
  return (
    <HashRouter>
      <div className="flex h-screen bg-slate-50 text-slate-900">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/log/:sid" element={<LogChat />} />
            <Route path="/ask/:sid" element={<Ask />} />
            <Route path="/preview/:sid" element={<Preview />} />
            <Route path="/notes" element={<Notes />} />
            <Route path="/notes/:id" element={<Notes />} />
            <Route path="/followup/:sid" element={<FollowUp />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}

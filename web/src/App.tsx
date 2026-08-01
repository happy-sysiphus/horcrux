import { HashRouter, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Home from "./pages/Home";

function Placeholder({ name }: { name: string }) {
  return <div className="p-8 text-slate-500">{name}</div>;
}

export default function App() {
  return (
    <HashRouter>
      <div className="flex h-screen bg-slate-50 text-slate-900">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/log/:sid" element={<Placeholder name="기록" />} />
            <Route path="/ask/:sid" element={<Placeholder name="질문" />} />
            <Route path="/preview/:sid" element={<Placeholder name="미리보기" />} />
            <Route path="/notes" element={<Placeholder name="연구노트" />} />
            <Route path="/notes/:id" element={<Placeholder name="연구노트" />} />
            <Route path="/followup/:sid" element={<Placeholder name="후속 실험" />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}

import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

export default function Onboarding() {
  const { refreshLab, signOut } = useAuth();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(f: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await f(); await refreshLab(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md space-y-4">
        <div className="text-center text-xl font-bold">소속 연구실 설정</div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="font-semibold">연구실 만들기</div>
          <p className="mt-1 text-xs text-slate-500">새 연구실의 관리자가 됩니다.</p>
          <div className="mt-3 flex flex-col gap-2 md:flex-row">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="연구실 이름"
              className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" />
            <button onClick={() => void run(() => api.labCreate(name.trim()))} disabled={busy || !name.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-40">만들기</button>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="font-semibold">초대 코드로 합류</div>
          <p className="mt-1 text-xs text-slate-500">관리자에게 받은 코드를 입력하세요.</p>
          <div className="mt-3 flex flex-col gap-2 md:flex-row">
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="초대 코드"
              className="min-w-0 flex-1 rounded border border-slate-300 px-3 py-2 text-sm" />
            <button onClick={() => void run(() => api.labJoin(code.trim()))} disabled={busy || !code.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-40">합류</button>
          </div>
        </div>
        {error && <div className="text-center text-sm text-red-600">{error}</div>}
        <button onClick={() => void signOut()} className="w-full text-center text-xs text-slate-400 underline">
          다른 계정으로 로그인
        </button>
      </div>
    </div>
  );
}

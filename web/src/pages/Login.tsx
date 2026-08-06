import { useAuth } from "../auth";

export default function Login() {
  const { signIn } = useAuth();
  // 구글/Supabase에서 실패해 돌아오면 ?error=...&error_description=... 이 실려 온다 —
  // 조용한 루프 대신 원문을 그대로 보여준다
  const q = new URLSearchParams(window.location.search);
  const err = q.get("error_description") || q.get("error");
  return (
    <div className="flex h-screen w-full items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-xs rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-xl text-white">⚗</span>
        <div className="mt-3 text-xl font-bold">LAB GENE</div>
        <p className="mt-1 text-sm text-slate-500">연구실 실험 기록·진단</p>
        <button onClick={() => void signIn()}
          className="mt-6 w-full rounded-lg border border-slate-300 py-2.5 text-sm font-medium hover:bg-slate-50">
          구글로 계속하기
        </button>
        {err && <p className="mt-3 break-words text-xs text-red-600">{err}</p>}
      </div>
    </div>
  );
}

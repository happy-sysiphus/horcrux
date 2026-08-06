import { useAuth } from "../auth";

export default function Login() {
  const { signIn } = useAuth();
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
      </div>
    </div>
  );
}

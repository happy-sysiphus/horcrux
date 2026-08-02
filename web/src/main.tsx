import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// 렌더 에러 시 React 18은 루트 전체를 unmount해 하얀 화면이 된다.
// 최소 ErrorBoundary로 에러 내용을 보여주고 복구 경로(새로고침·세션 초기화)를 제공.
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-8 text-slate-900">
        <p className="text-lg font-semibold">화면 표시 중 오류가 발생했습니다</p>
        <pre className="max-h-48 max-w-2xl overflow-auto rounded bg-slate-100 p-3 text-xs text-red-600">
          {String(this.state.error?.stack ?? this.state.error)}
        </pre>
        <div className="flex gap-2">
          <button
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white"
            onClick={() => { location.hash = "#/"; location.reload(); }}
          >
            홈으로 새로고침
          </button>
          <button
            className="rounded border border-slate-300 px-4 py-2 text-sm"
            onClick={() => {
              localStorage.removeItem("labgene.sessions.v1");
              location.hash = "#/"; location.reload();
            }}
          >
            대화 기록 초기화 후 재시작
          </button>
        </div>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);

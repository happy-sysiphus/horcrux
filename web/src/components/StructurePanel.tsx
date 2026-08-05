import type { ParsedLog } from "../types";

function Row({ label, value }: { label: string; value: string }) {
  return value ? (
    <div className="mt-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-sm font-medium whitespace-pre-wrap">{value}</div>
    </div>
  ) : null;
}

export default function StructurePanel({ parsed, gaps, requiredTotal, canSave, onSaveClick, saveLabel, className = "" }: {
  parsed: ParsedLog | null;
  gaps: string[];          // 마지막 파싱 기준 누락 항목 전체 (게이지 분자 계산)
  requiredTotal: number;
  canSave: boolean;        // 질문 루프 소진 또는 재질문 라운드 소진
  onSaveClick: () => void;
  saveLabel: string;
  className?: string;      // 모바일 탭 전환용 표시/숨김
}) {
  const done = Math.max(requiredTotal - gaps.length, 0);
  return (
    <div className={`min-h-0 w-full flex-1 flex-col border-slate-200 bg-white p-5 md:h-full md:w-80 md:flex-none md:shrink-0 md:border-l ${className}`}>
      <div className="text-lg font-bold">연구 기록</div>
      <div className="text-xs text-slate-400">실시간으로 구조화됩니다.</div>
      <div className="flex-1 overflow-y-auto">
        {!parsed && <div className="mt-8 text-sm text-slate-400">첫 메시지를 보내면 구조화가 시작됩니다.</div>}
        {parsed && (
          <>
            <Row label="실험 목적" value={parsed.objective} />
            <Row label="실험 유형" value={parsed.experiment_type} />
            <Row label="장비" value={parsed.equipment.join(", ")} />
            <Row label="재료" value={parsed.materials.join(", ")} />
            <Row label="조건" value={parsed.parameters.map((p) => `${p.name} ${p.value}`).join(" · ")} />
            <Row label="결과" value={parsed.results} />
            <Row label="증상" value={parsed.symptom.category === "none" ? "문제 없음" : parsed.symptom.description} />
            <Row label="조치" value={parsed.actions_taken.join(", ")} />
            {gaps.length > 0 && (
              <div className="mt-4">
                <div className="text-xs text-slate-400">누락 정보</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {gaps.map((g) => (
                    <span key={g} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                      {g.slice(0, 20)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">정보 완성도</span>
                <span data-testid="gauge-text" className="font-medium text-blue-600">{done} / {requiredTotal}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-blue-600"
                  style={{ width: `${requiredTotal ? (done / requiredTotal) * 100 : 0}%` }} />
              </div>
            </div>
          </>
        )}
      </div>
      <button onClick={onSaveClick} disabled={!parsed || !canSave}
        className="mt-4 rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white disabled:opacity-40">
        {saveLabel}
      </button>
      {parsed && !canSave && (
        <div className="mt-1 text-center text-xs text-slate-400">남은 질문에 답하면 저장할 수 있어요</div>
      )}
    </div>
  );
}

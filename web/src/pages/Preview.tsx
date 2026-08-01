import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { getSession, saveSession } from "../store";
import { symptomCategoryLabels } from "../types";
import type { ParsedLog, RecordDetail } from "../types";

function Field({ label, value, onChange, onBlur, rows = 1 }: {
  label: string; value: string; onChange: (v: string) => void; onBlur?: () => void; rows?: number;
}) {
  return (
    <label className="block">
      <div className="text-xs text-slate-400">{label}</div>
      <textarea value={value} rows={rows} onChange={(e) => onChange(e.target.value)} onBlur={onBlur}
        className="mt-1 w-full resize-none rounded border border-slate-200 px-2 py-1.5 text-sm font-medium" />
    </label>
  );
}

function parseParameters(text: string): ParsedLog["parameters"] {
  return text.split(",").map((x) => x.trim()).filter((x) => x.includes("=")).map((x) => {
    const [name, ...rest] = x.split("=");
    return { name: name.trim(), value: rest.join("=").trim(), controllable: true };
  });
}

const csv = {
  serialize: (v: string[]) => v.join(", "),
  parse: (text: string) => text.split(",").map((x) => x.trim()).filter(Boolean),
};

// 쉼표 구분 텍스트 필드 공통 컴포넌트. typing 중 매 keystroke마다 파싱하면 "=" 없는(또는
// 아직 비어 있는) 중간 세그먼트가 즉시 버려져 기존 값이 뭉개진다. 그래서 draft는 로컬로만
// 들고, blur 시점에만 parse+onCommit으로 실제 값에 반영한다.
function DraftField<T>({ label, value, serialize, parse, onCommit, rows = 1 }: {
  label: string; value: T; serialize: (v: T) => string; parse: (text: string) => T;
  onCommit: (v: T) => void; rows?: number;
}) {
  const [draft, setDraft] = useState(() => serialize(value));
  // 다른 필드 편집 등 외부 요인으로 value의 참조가 바뀌면 draft를 재동기화한다.
  useEffect(() => setDraft(serialize(value)), [value]);
  return (
    <Field label={label} value={draft} rows={rows} onChange={setDraft}
      onBlur={() => onCommit(parse(draft))} />
  );
}

export default function Preview() {
  const { sid } = useParams();
  const nav = useNavigate();
  const session = getSession(sid ?? "");
  const [p, setP] = useState<ParsedLog | null>(session?.parsed ?? null);
  const [base, setBase] = useState<RecordDetail | null>(null);
  const [updateBase, setUpdateBase] = useState(false);
  const [baseCause, setBaseCause] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);  // 저장 성공 후 재시도 시 중복 생성 방지

  useEffect(() => {
    if (session?.baseId) api.getRecord(session.baseId).then(setBase).catch(() => {});
  }, [session?.baseId]);

  if (!session || !p) return <div className="p-8 text-slate-500">미리볼 파싱 결과가 없습니다.</div>;
  if (session.saved && !savedId)
    return (
      <div className="p-8 text-slate-500">
        이미 저장된 대화입니다.{" "}
        <button onClick={() => nav("/notes")} className="text-blue-600 underline">연구노트에서 보기</button>
      </div>
    );
  const set = (patch: Partial<ParsedLog>) => setP({ ...p, ...patch });
  const showBaseUpdate = base && !base.record.resolution.resolved;

  async function onSave() {
    setBusy(true);
    setError(null);
    try {
      // 레코드는 한 번만 생성 — feedback 실패 후 재시도해도 중복 레코드가 생기지 않게 id 보관
      let id = savedId;
      if (!id) {
        id = (await api.saveRecord(session!.rawText, p!, session!.baseId)).id;
        setSavedId(id);
        session!.saved = true;
        saveSession(session!);
      }
      if (updateBase && session!.baseId && baseCause.trim())
        await api.feedback(session!.baseId, true, baseCause.trim());
      nav(`/notes/${id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <h1 className="text-2xl font-bold">저장 전 기록 미리보기</h1>
      <p className="text-sm text-slate-500">AI가 정리한 내용을 확인하고 수정하세요.</p>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="font-semibold">기본 정보</div>
          <Field label="실험 유형" value={p.experiment_type} onChange={(v) => set({ experiment_type: v })} />
          <Field label="실험 목적" value={p.objective} onChange={(v) => set({ objective: v })} />
          <DraftField label="장비 (쉼표 구분)" value={p.equipment} serialize={csv.serialize} parse={csv.parse}
            onCommit={(equipment) => set({ equipment })} />
          <DraftField label="재료 (쉼표 구분)" value={p.materials} serialize={csv.serialize} parse={csv.parse}
            onCommit={(materials) => set({ materials })} />
        </div>
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="font-semibold">조건·결과</div>
          <DraftField label="공정변수 (이름=값, 쉼표 구분)" value={p.parameters}
            serialize={(v) => v.map((x) => `${x.name}=${x.value}`).join(", ")}
            parse={parseParameters}
            onCommit={(parameters) => set({ parameters })} />
          <Field label="결과" value={p.results} rows={2} onChange={(v) => set({ results: v })} />
          <label className="block">
            <div className="text-xs text-slate-400">증상 분류</div>
            <select value={p.symptom.category}
              onChange={(e) => set({ symptom: { ...p.symptom, category: e.target.value as ParsedLog["symptom"]["category"] } })}
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm font-medium">
              {Object.entries(symptomCategoryLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <Field label="증상 설명" value={p.symptom.description} rows={2}
            onChange={(v) => set({ symptom: { ...p.symptom, description: v } })} />
          <DraftField label="조치 (쉼표 구분)" value={p.actions_taken} serialize={csv.serialize} parse={csv.parse}
            onCommit={(actions_taken) => set({ actions_taken })} />
          <DraftField label="원인 후보 (쉼표 구분 — 피드백 시 확정 원인 선택지가 됨)" value={p.suspected_causes}
            serialize={(v) => v.map((c) => c.cause).join(", ")}
            parse={(text) => csv.parse(text).map((cause) => ({ cause, status: "unconfirmed" as const }))}
            onCommit={(suspected_causes) => set({ suspected_causes })} />
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="font-semibold">정리 요약</div>
        <Field label="요약" value={p.summary} rows={3} onChange={(v) => set({ summary: v })} />
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-slate-500">원문 로그 (읽기 전용)</summary>
          <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{session.rawText}</pre>
        </details>
      </div>

      {showBaseUpdate && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
          <label className="flex items-center gap-2 font-medium">
            <input type="checkbox" checked={updateBase} onChange={(e) => setUpdateBase(e.target.checked)} />
            기준 실험({base!.record.id})의 원인 상태 업데이트 — 미확정 ➔ 확인됨
          </label>
          {updateBase && (
            <div className="mt-3 flex flex-wrap gap-2">
              {base!.record.suspected_causes.map((c) => (
                <button key={c.cause} onClick={() => setBaseCause(c.cause)}
                  className={`rounded-full border px-3 py-1 text-sm ${baseCause === c.cause ? "border-emerald-600 bg-white font-medium" : "border-slate-300 bg-white"}`}>
                  {c.cause}
                </button>
              ))}
              <input value={baseCause} onChange={(e) => setBaseCause(e.target.value)}
                placeholder="확정 원인 직접 입력" className="rounded border border-slate-300 px-2 py-1 text-sm" />
            </div>
          )}
        </div>
      )}

      <div className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-blue-800">
        ⑂ 저장하면 자동으로 생성됩니다 — 위키 아티클(백그라운드 편찬)
      </div>

      {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
      <div className="mt-6 flex justify-end gap-3">
        <button onClick={() => nav(-1)} className="rounded-lg border border-slate-300 bg-white px-5 py-2 text-sm">
          수정하기 (대화로 돌아가기)
        </button>
        <button onClick={onSave} disabled={busy}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "저장 중..." : "저장하기"}
        </button>
      </div>
    </div>
  );
}

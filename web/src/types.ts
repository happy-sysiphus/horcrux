export interface Parameter { name: string; value: string; controllable: boolean }
export interface Symptom {
  category: "low_value" | "unstable" | "abnormal" | "none";
  description: string;
}
export interface SuspectedCause {
  cause: string;
  status: "unconfirmed" | "confirmed" | "rejected";
}
export interface Resolution { resolved: boolean; actual_cause: string | null; note: string }

export interface ParsedLog {
  experiment_type: string;
  objective: string;
  equipment: string[];
  materials: string[];
  parameters: Parameter[];
  results: string;
  symptom: Symptom;
  suspected_causes: SuspectedCause[];
  actions_taken: string[];
  summary: string;
  unrecorded_required_parameters: string[];
}

export interface RecordMeta {
  id: string; date: string; experiment_type: string; objective: string;
  equipment: string[]; materials: string[]; symptom: Symptom;
  resolution: Resolution; needs_review: boolean; followup_of: string | null;
}
export interface RecordDetail {
  record: RecordMeta & {
    parameters: Parameter[]; results: string;
    suspected_causes: SuspectedCause[]; actions_taken: string[];
  };
  body: string;
}
export interface AskResult {
  answer: string;
  evidence: "records" | "wiki" | "none";
  records: Pick<RecordMeta, "id" | "date" | "experiment_type" | "objective" | "symptom" | "resolution">[];
  wiki: string[];
}
export interface AppConfig {
  required_fields: string[]; required_parameters: string[];
  provider: string; vault: string;
}

export interface ChatMsg { role: "user" | "ai"; text: string; chips?: string[] }
export interface Session {
  id: string;
  kind: "log" | "ask" | "followup";
  title: string;
  createdAt: number;
  saved: boolean;          // 레코드로 저장 완료 여부 (log/followup)
  baseId?: string;         // followup: 기준 레코드 id
  rawText: string;         // 누적 원문
  messages: ChatMsg[];
  parsed: ParsedLog | null;
  gaps: string[];
  gapIndex: number;        // 현재 질문 중인 gap
  answers: string[];       // 로컬 누적 답변 (재파싱 전)
  rounds: number;          // 재파싱 횟수 (최대 3)
  askResult?: AskResult;
}

export interface Parameter { name: string; value: string; controllable: boolean }
export interface Symptom {
  category: "low_value" | "unstable" | "abnormal" | "none";
  description: string;
}
export const symptomCategoryLabels: Record<Symptom["category"], string> = {
  none: "문제 없음",
  low_value: "값이 낮음",
  unstable: "불안정·재현성",
  abnormal: "비정상 거동",
};
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

export interface Reference {
  type: "paper" | "link" | "record" | "pdf";  // pdf는 파일 첨부 스펙에서 사용 예정
  title: string;
  url: string;
  record_id: string;
}

export interface RecordMeta {
  id: string; date: string; experiment_type: string; objective: string;
  equipment: string[]; materials: string[]; symptom: Symptom;
  resolution: Resolution; needs_review: boolean; followup_of: string | null;
  references?: Reference[];   // 백엔드 병합 전 응답엔 없다 — 읽는 쪽에서 ?? []
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
// 사용자 발화 직전의 대화 상태 — 되감기·포크의 복원 지점
export interface ConvoSnapshot {
  rawText: string; messages: ChatMsg[]; parsed: ParsedLog | null;
  gaps: string[]; gapIndex: number; answers: string[]; rounds: number;
}
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
  history?: ConvoSnapshot[]; // n번째 = n+1번째 사용자 발화 직전 상태 (초기 로그 제외)
}

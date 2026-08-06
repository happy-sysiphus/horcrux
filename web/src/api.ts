import type { AppConfig, AskResult, ParsedLog, RecordDetail, RecordMeta, Reference } from "./types";

async function http<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `요청 실패 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  parse: (text: string) =>
    http<{ parsed: ParsedLog; gaps: string[] }>("POST", "/api/parse", { text }),
  saveRecord: (text: string, parsed: ParsedLog, followupOf?: string) =>
    http<{ id: string; path: string }>("POST", "/api/records",
      { text, parsed, followup_of: followupOf ?? null }),
  saveRaw: (text: string) =>
    http<{ id: string; path: string }>("POST", "/api/records/raw", { text }),
  ask: (text: string) => http<AskResult>("POST", "/api/ask", { text }),
  listRecords: () => http<{ records: RecordMeta[] }>("GET", "/api/records"),
  getRecord: (id: string) => http<RecordDetail>("GET", `/api/records/${id}`),
  feedback: (recordId: string, resolved: boolean, cause?: string, note?: string) =>
    http<{ message: string }>("POST", "/api/feedback",
      { record_id: recordId, resolved, cause: cause ?? null, note: note ?? "" }),
  putReferences: (recordId: string, references: Reference[]) =>
    http<{ record: RecordMeta }>("PUT", `/api/records/${recordId}/references`, { references }),
  config: () => http<AppConfig>("GET", "/api/config"),
};

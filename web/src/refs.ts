// DOI 정규화·Crossref 제목 조회 — UI와 무관한 순수 모듈
export function normalizeDoi(input: string): string | null {
  const s = input.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  return /^10\.\S+\/\S+$/.test(s) ? `https://doi.org/${s}` : null;
}

// "제목 (성, 연도)" 조합. 실패는 throw — 호출부(폼)가 잡아 안내하고 수동 입력 지속.
export async function fetchDoiTitle(doiUrl: string): Promise<string> {
  const doi = doiUrl.replace("https://doi.org/", "");
  const res = await fetch(`https://api.crossref.org/works/${encodeURIComponent(doi)}`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) throw new Error(`조회 실패 (${res.status})`);
  const m = (await res.json()).message;
  const title: string = m.title?.[0] ?? "";
  if (!title) throw new Error("제목 정보 없음");
  const author: string | undefined = m.author?.[0]?.family;
  const year: number | undefined = m.issued?.["date-parts"]?.[0]?.[0];
  const suffix = author && year ? ` (${author}, ${year})` : author ? ` (${author})` : year ? ` (${year})` : "";
  return title + suffix;
}

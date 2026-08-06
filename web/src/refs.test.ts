import { describe, expect, it } from "vitest";
import { normalizeDoi } from "./refs";

describe("normalizeDoi", () => {
  it("bare DOI를 doi.org URL로", () => {
    expect(normalizeDoi(" 10.1063/1.4757907 ")).toBe("https://doi.org/10.1063/1.4757907");
  });
  it("doi.org URL 붙여넣기 허용 (dx., http 포함)", () => {
    expect(normalizeDoi("https://dx.doi.org/10.1063/1.4757907")).toBe("https://doi.org/10.1063/1.4757907");
  });
  it("DOI 패턴이 아니면 null", () => {
    expect(normalizeDoi("https://example.com/manual.pdf")).toBeNull();
    expect(normalizeDoi("논문 제목")).toBeNull();
  });
});

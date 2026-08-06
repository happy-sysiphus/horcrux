import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReferencesSection from "./ReferencesSection";

describe("ReferencesSection", () => {
  it("참조 목록을 렌더하고 없는 레코드를 표시한다", () => {
    render(<ReferencesSection recordId="r1" records={[]}
      onSaved={() => {}} onOpenRecord={() => {}}
      references={[
        { type: "paper", title: "ALD 논문 (Kim, 2020)", url: "https://doi.org/10.1/x", record_id: "" },
        { type: "record", title: "", url: "", record_id: "삭제된것" },
      ]} />);
    expect(screen.getByText(/ALD 논문/)).toBeTruthy();
    expect(screen.getByText(/없는 레코드/)).toBeTruthy();
  });
});

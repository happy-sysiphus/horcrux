import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Settings from "./Settings";

vi.mock("../auth", () => ({
  useAuth: () => ({
    me: {
      lab: { id: "l1", name: "산화막랩", llm_mode: "central", llm_provider: null,
             daily_llm_limit: 200, invite_code: "abcd1234" },
      role: "admin", usage_today: 3,
      members: [{ user_id: "u1", email: "a@b.c", role: "admin" }],
    },
    refreshLab: async () => {},
  }),
}));

describe("Settings", () => {
  it("초대 코드·사용량·멤버를 렌더한다", () => {
    render(<Settings />);
    expect(screen.getByText("abcd1234")).toBeTruthy();
    expect(screen.getByText("3 / 200")).toBeTruthy();
    expect(screen.getByText("a@b.c")).toBeTruthy();
  });

  it("일일 상한은 편집할 수 없다 — 운영자 전용", () => {
    const { container } = render(<Settings />);
    expect(container.querySelector('input[type="number"]')).toBeNull();
  });
});

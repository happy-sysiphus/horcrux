import { render, screen } from "@testing-library/react";
import StructurePanel from "./StructurePanel";
import type { ParsedLog } from "../types";

const parsed: ParsedLog = {
  experiment_type: "증착", objective: "막 50nm", equipment: ["ALD-02"], materials: [],
  parameters: [{ name: "온도", value: "250C", controllable: true }], results: "",
  symptom: { category: "none", description: "" }, suspected_causes: [],
  actions_taken: [], summary: "", unrecorded_required_parameters: [],
};

test("게이지가 (전체-누락)/전체 를 표시한다", () => {
  render(<StructurePanel parsed={parsed} gaps={["결과?", "조치?"]} requiredTotal={5}
    canSave={false} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  expect(screen.getByTestId("gauge-text").textContent).toBe("3 / 5");
});

test("질문 루프가 안 끝나면 저장 버튼 비활성", () => {
  render(<StructurePanel parsed={parsed} gaps={["결과?"]} requiredTotal={5}
    canSave={false} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  expect((screen.getByRole("button", { name: "검토 후 저장" }) as HTMLButtonElement).disabled)
    .toBe(true);
});

test("파싱 전에는 저장 버튼 비활성", () => {
  render(<StructurePanel parsed={null} gaps={[]} requiredTotal={5}
    canSave={true} onSaveClick={() => {}} saveLabel="검토 후 저장" />);
  // jest-dom 매처(toBeDisabled)는 의존성 추가가 필요하므로 내장 매처만 사용
  expect((screen.getByRole("button", { name: "검토 후 저장" }) as HTMLButtonElement).disabled)
    .toBe(true);
});

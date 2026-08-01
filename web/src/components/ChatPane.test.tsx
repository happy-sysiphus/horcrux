import { fireEvent, render, screen } from "@testing-library/react";
import ChatPane from "./ChatPane";
import type { ChatMsg } from "../types";

const msgs: ChatMsg[] = [
  { role: "user", text: "오늘 증착했어" },
  { role: "ai", text: "문제나 이상 증상이 있었나요?", chips: ["문제 없음", "건너뛰기"] },
];

test("마지막 AI 메시지의 칩을 누르면 그 텍스트로 전송된다", () => {
  const sent: string[] = [];
  render(<ChatPane messages={msgs} onSend={(t) => sent.push(t)} busy={false} />);
  fireEvent.click(screen.getByRole("button", { name: "건너뛰기" }));
  expect(sent).toEqual(["건너뛰기"]);
});

test("처리 중(busy)에는 칩이 표시되지 않는다", () => {
  render(<ChatPane messages={msgs} onSend={() => {}} busy={true} />);
  expect(screen.queryByRole("button", { name: "건너뛰기" })).toBeNull();
});

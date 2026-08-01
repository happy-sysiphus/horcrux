import { diffParameters, toEntries } from "./DiffPanel";

test("변경·유지·신규 변수를 구분한다", () => {
  const base = [
    { name: "온도", value: "250C", controllable: true },
    { name: "전구체", value: "TMA(개봉 7일)", controllable: true },
  ];
  const current = [
    { name: "온도", value: "250C", controllable: true },
    { name: "전구체", value: "TMA(신규)", controllable: true },
    { name: "압력", value: "1Torr", controllable: true },
  ];
  const d = diffParameters(base, current);
  expect(d.kept).toEqual([{ name: "온도", value: "250C" }]);
  expect(d.changed).toEqual([{ name: "전구체", from: "TMA(개봉 7일)", to: "TMA(신규)" }]);
  expect(d.added).toEqual([{ name: "압력", value: "1Torr" }]);
});

test("장비·재료 변경도 diff에 잡힌다 (스펙 ⑦)", () => {
  const d = diffParameters(
    toEntries(["ALD-02"], ["TMA"], []),
    toEntries(["ALD-03"], ["TMA"], []));
  expect(d.changed).toEqual([{ name: "장비", from: "ALD-02", to: "ALD-03" }]);
  expect(d.kept).toEqual([{ name: "재료", value: "TMA" }]);
});

import { describe, expect, it } from "vitest";
import { buildGraph } from "./graph";
import type { RecordMeta } from "./types";

function mk(over: Partial<RecordMeta>): RecordMeta {
  return {
    id: "r1", date: "2026-08-01", experiment_type: "증착", objective: "",
    equipment: [], materials: [],
    symptom: { category: "none", description: "" },
    resolution: { resolved: false, actual_cause: null, note: "" },
    needs_review: false, followup_of: null,
    ...over,
  };
}

describe("buildGraph", () => {
  it("여러 레코드의 같은 장비·재료는 하나의 노드로 합친다", () => {
    const { nodes, links } = buildGraph([
      mk({ id: "a", equipment: ["ALD-02"], materials: [" TMA "] }),
      mk({ id: "b", equipment: ["ALD-02"], materials: ["TMA"] }),
    ]);
    const eq = nodes.filter((n) => n.kind === "equipment");
    const mat = nodes.filter((n) => n.kind === "material");
    expect(eq).toHaveLength(1);
    expect(eq[0].recIds).toEqual(["a", "b"]);
    expect(mat).toHaveLength(1); // trim 후 동일
    expect(links).toHaveLength(4);
  });

  it("확정 원인만 노드가 되고 긴 라벨은 잘린다", () => {
    const long = "전구체 열화가 원인이었다. 개봉 후 12일이 지나 활성도가 떨어진 것으로 확인".repeat(2);
    const { nodes } = buildGraph([
      mk({ id: "a", resolution: { resolved: true, actual_cause: long, note: "" } }),
      mk({ id: "b", resolution: { resolved: false, actual_cause: "미확정 추측", note: "" } }),
    ]);
    const causes = nodes.filter((n) => n.kind === "cause");
    expect(causes).toHaveLength(1);
    expect(causes[0].label.length).toBeLessThanOrEqual(31);
    expect(causes[0].label.endsWith("…")).toBe(true);
    expect(causes[0].full).toBe(long);
  });

  it("followup_of 엣지는 대상 레코드가 있을 때만 만든다", () => {
    const { links } = buildGraph([
      mk({ id: "base" }),
      mk({ id: "next", followup_of: "base" }),
      mk({ id: "orphan", followup_of: "없는레코드" }),
    ]);
    expect(links).toEqual([{ source: "base", target: "next" }]);
  });

  it("빈 문자열 엔티티와 중복 엣지는 버린다", () => {
    const { nodes, links } = buildGraph([
      mk({ id: "a", equipment: ["", "  ", "RIE-01", "RIE-01"] }),
    ]);
    expect(nodes.filter((n) => n.kind === "equipment")).toHaveLength(1);
    expect(links).toHaveLength(1);
  });
});

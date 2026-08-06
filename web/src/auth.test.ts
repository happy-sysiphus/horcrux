import { describe, expect, it } from "vitest";
import { resolveRoute } from "./auth";

describe("resolveRoute", () => {
  it("로컬 모드는 항상 앱", () => expect(resolveRoute("local", false, false)).toBe("app"));
  it("배포 + 미로그인 → 로그인", () => expect(resolveRoute("deploy", false, false)).toBe("login"));
  it("배포 + 로그인 + 무소속 → 온보딩", () => expect(resolveRoute("deploy", true, false)).toBe("onboarding"));
  it("배포 + 로그인 + 소속 → 앱", () => expect(resolveRoute("deploy", true, true)).toBe("app"));
});

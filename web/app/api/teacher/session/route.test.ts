import { afterEach, describe, expect, it, vi } from "vitest";
import { DELETE, POST } from "./route";

const request = (credential: string) => new Request("http://localhost:3000/api/teacher/session", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential }),
});

describe("teacher session route", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("fails closed without configuration and rejects a wrong credential generically", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "");
    expect((await POST(request("anything"))).status).toBe(503);
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "expected-access");
    const response = await POST(request("wrong-access"));
    expect(response.status).toBe(401);
    expect(await response.text()).not.toContain("expected-access");
  });

  it("sets a signed HttpOnly strict cookie without the raw token", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "expected-access");
    vi.stubEnv("NODE_ENV", "development");
    const response = await POST(request("expected-access"));
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(response.status).toBe(200);
    expect(cookie).toMatch(/exam_teacher_session=/);
    expect(cookie.toLowerCase()).toContain("httponly");
    expect(cookie.toLowerCase()).toContain("samesite=strict");
    expect(cookie.toLowerCase()).not.toContain("secure");
    expect(cookie).not.toContain("expected-access");
  });

  it("uses Secure in production and logout expires the session", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "expected-access");
    vi.stubEnv("NODE_ENV", "production");
    expect((await POST(request("expected-access"))).headers.get("set-cookie")?.toLowerCase()).toContain("secure");
    const logout = await DELETE();
    expect(logout.headers.get("set-cookie")).toMatch(/Max-Age=0/i);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { createTeacherSession, TEACHER_SESSION_SECONDS, validateTeacherCredential, verifyTeacherSession } from "./teacher-auth";

describe("teacher session security", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("fails closed when UI access configuration is missing", () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "");
    expect(validateTeacherCredential("anything")).toBe(false);
    expect(verifyTeacherSession("anything")).toBe(false);
    expect(() => createTeacherSession()).toThrow();
  });

  it("signs a session that contains neither the raw credential nor a reusable secret", () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "top-secret-access");
    const now = Date.UTC(2026, 8, 17, 12);
    const session = createTeacherSession(now);
    expect(session).not.toContain("top-secret-access");
    expect(verifyTeacherSession(session, now + 1_000)).toBe(true);
    expect(verifyTeacherSession(`${session}tampered`, now + 1_000)).toBe(false);
    expect(verifyTeacherSession(session, now + TEACHER_SESSION_SECONDS * 1_000)).toBe(false);
  });
});

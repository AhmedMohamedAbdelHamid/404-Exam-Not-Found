import { afterEach, describe, expect, it, vi } from "vitest";
import { createTeacherSession, TEACHER_SESSION_COOKIE } from "@/lib/teacher-auth";
import { GET } from "./route";

const liveTeacherData = {
  data_source: "live", data_status: "available",
  summary: { total_students: 1, total_attempts: 1, completed_attempts: 1, in_progress_attempts: 0, completion_rate: 100, confirmed_answers: 1, correct_answers: 1, incorrect_answers: 0, overall_accuracy: 100, average_score: 1, average_difficulty: 3, misconception_count: 0 },
  topics: [{ topic: "functions", attempted: 1, correct: 1, incorrect: 0, accuracy: 100 }],
  misconceptions: [],
  difficulty: [1, 2, 3, 4, 5].map((difficulty) => ({ difficulty, count: difficulty === 3 ? 1 : 0 })),
  score_distribution: [{ band: "0–20%", attempts: 0 }, { band: "21–40%", attempts: 0 }, { band: "41–60%", attempts: 0 }, { band: "61–80%", attempts: 0 }, { band: "81–100%", attempts: 1 }],
  students: [{ attempt_id: "attempt-1", student_id: "student", language: "en", status: "completed", answered: 1, correct: 1, incorrect: 0, accuracy: 100, initial_difficulty: 3, final_difficulty: 4, created_at: "2026-09-17T10:00:00Z", completed_at: "2026-09-17T10:05:00Z" }],
};

function authorizedRequest() {
  return new Request("http://localhost:3000/api/teacher/live", { headers: { cookie: `${TEACHER_SESSION_COOKIE}=${createTeacherSession()}` } });
}

describe("live teacher proxy", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllEnvs(); });

  it("rejects missing or tampered sessions", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access");
    expect((await GET(new Request("http://localhost:3000/api/teacher/live"))).status).toBe(401);
    expect((await GET(new Request("http://localhost:3000/api/teacher/live", { headers: { cookie: `${TEACHER_SESSION_COOKIE}=tampered` } }))).status).toBe(401);
  });

  it("fails closed when the backend token is missing", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access");
    vi.stubEnv("TEACHER_DASHBOARD_TOKEN", "");
    expect((await GET(authorizedRequest())).status).toBe(503);
  });

  it("calls FastAPI once with server-side Bearer auth and returns only validated analytics", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access");
    vi.stubEnv("TEACHER_DASHBOARD_TOKEN", "backend-secret");
    vi.stubEnv("API_INTERNAL_BASE_URL", "http://127.0.0.1:8000");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(liveTeacherData), { status: 200, headers: { "Content-Type": "application/json" } }));
    const response = await GET(authorizedRequest());
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [target, init] = fetchMock.mock.calls[0];
    expect(String(target)).toBe("http://127.0.0.1:8000/api/teacher/live");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer backend-secret");
    const body = await response.text();
    expect(body).not.toContain("backend-secret");
    const payload = JSON.parse(body) as Record<string, unknown>;
    expect(Object.hasOwn(payload, "correct_answer")).toBe(false);
    expect(Object.hasOwn(payload, "selected_answer")).toBe(false);
    expect(Object.hasOwn(payload, "question")).toBe(false);
  });

  it.each([401, 503])("normalizes FastAPI %s without exposing upstream details", async (status) => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access"); vi.stubEnv("TEACHER_DASHBOARD_TOKEN", "backend-secret");
    vi.stubEnv("API_INTERNAL_BASE_URL", "http://127.0.0.1:8000");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("secret upstream detail", { status }));
    const response = await GET(authorizedRequest());
    expect([502, 503]).toContain(response.status);
    expect(await response.text()).not.toContain("secret upstream detail");
  });

  it("handles network failure and malformed JSON safely", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access"); vi.stubEnv("TEACHER_DASHBOARD_TOKEN", "backend-secret");
    vi.stubEnv("API_INTERNAL_BASE_URL", "http://127.0.0.1:8000");
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("internal URL leaked"));
    expect((await GET(authorizedRequest())).status).toBe(503);
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ data_source: "live" }), { status: 200 }));
    expect((await GET(authorizedRequest())).status).toBe(502);
  });

  it("rejects an internal URL that would recurse into the Next.js route", async () => {
    vi.stubEnv("TEACHER_UI_ACCESS_TOKEN", "ui-access"); vi.stubEnv("TEACHER_DASHBOARD_TOKEN", "backend-secret");
    vi.stubEnv("API_INTERNAL_BASE_URL", "http://localhost:3000");
    const fetchMock = vi.spyOn(globalThis, "fetch");
    expect((await GET(authorizedRequest())).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

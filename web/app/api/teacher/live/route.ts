import { NextResponse } from "next/server";
import { teacherLiveSchema } from "@/lib/api";
import { readCookie, TEACHER_SESSION_COOKIE, verifyTeacherSession } from "@/lib/teacher-auth";

function error(status: number, code: string, message: string, retryable = false) {
  return NextResponse.json({ error: { code, message, retryable } }, { status });
}

function backendEndpoint(requestUrl: string): URL | null {
  const configured = process.env.API_INTERNAL_BASE_URL
    ?? process.env.NEXT_PUBLIC_API_BASE_URL
    ?? "http://127.0.0.1:8000";
  try {
    const base = new URL(configured);
    if (!(["http:", "https:"] as string[]).includes(base.protocol)) return null;
    if (base.username || base.password) return null;
    const endpoint = new URL("/api/teacher/live", base);
    if (endpoint.origin === new URL(requestUrl).origin) return null;
    return endpoint;
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  const session = readCookie(request.headers.get("cookie"), TEACHER_SESSION_COOKIE);
  if (!verifyTeacherSession(session)) {
    return error(401, "TEACHER_SESSION_REQUIRED", "Teacher access is required.");
  }
  const backendToken = process.env.TEACHER_DASHBOARD_TOKEN?.trim();
  if (!backendToken) {
    return error(503, "TEACHER_PROXY_NOT_CONFIGURED", "Live teacher analytics is not configured.");
  }
  const endpoint = backendEndpoint(request.url);
  if (!endpoint) {
    return error(503, "TEACHER_PROXY_NOT_CONFIGURED", "Live teacher analytics is not configured.");
  }

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "GET",
      headers: { Authorization: `Bearer ${backendToken}`, Accept: "application/json" },
      cache: "no-store",
      redirect: "error",
    });
  } catch {
    return error(503, "TEACHER_SERVICE_UNAVAILABLE", "Live teacher analytics is temporarily unavailable.", true);
  }
  if (!response.ok) {
    return error(
      response.status === 401 ? 502 : 503,
      "TEACHER_SERVICE_UNAVAILABLE",
      "Live teacher analytics is temporarily unavailable.",
      true,
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  const parsed = teacherLiveSchema.safeParse(payload);
  if (!parsed.success) {
    return error(502, "TEACHER_RESPONSE_INVALID", "Live teacher analytics returned an invalid response.", true);
  }
  return NextResponse.json(parsed.data, {
    status: 200,
    headers: { "Cache-Control": "private, no-store" },
  });
}

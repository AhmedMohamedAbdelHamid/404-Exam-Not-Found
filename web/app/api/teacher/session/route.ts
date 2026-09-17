import { NextResponse } from "next/server";
import {
  createTeacherSession,
  TEACHER_SESSION_COOKIE,
  TEACHER_SESSION_SECONDS,
  teacherUiConfigured,
  validateTeacherCredential,
} from "@/lib/teacher-auth";

function error(status: number, code: string, message: string, retryable = false) {
  return NextResponse.json({ error: { code, message, retryable } }, { status });
}

export async function POST(request: Request) {
  if (!teacherUiConfigured()) {
    return error(503, "TEACHER_ACCESS_NOT_CONFIGURED", "Teacher access is not configured.");
  }
  const payload: unknown = await request.json().catch(() => null);
  const credential = payload && typeof payload === "object" && "credential" in payload
    ? (payload as { credential?: unknown }).credential
    : undefined;
  if (typeof credential !== "string" || !credential || !validateTeacherCredential(credential)) {
    return error(401, "TEACHER_ACCESS_DENIED", "The teacher credential is invalid.");
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set({
    name: TEACHER_SESSION_COOKIE,
    value: createTeacherSession(),
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: TEACHER_SESSION_SECONDS,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set({
    name: TEACHER_SESSION_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return response;
}

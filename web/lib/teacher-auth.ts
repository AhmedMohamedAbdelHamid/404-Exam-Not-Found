import { createHmac, createHash, timingSafeEqual } from "node:crypto";

export const TEACHER_SESSION_COOKIE = "exam_teacher_session";
export const TEACHER_SESSION_SECONDS = 8 * 60 * 60;

type SessionPayload = { version: 1; issuedAt: number; expiresAt: number };

function secret(): string | null {
  const configured = process.env.TEACHER_UI_ACCESS_TOKEN?.trim();
  return configured || null;
}

function signature(encodedPayload: string, key: string): string {
  return createHmac("sha256", key)
    .update(`exam-not-found:teacher-session:v1:${encodedPayload}`)
    .digest("base64url");
}

export function safeSecretEqual(candidate: string, expected: string): boolean {
  const candidateDigest = createHash("sha256").update(candidate).digest();
  const expectedDigest = createHash("sha256").update(expected).digest();
  return timingSafeEqual(candidateDigest, expectedDigest);
}

export function teacherUiConfigured(): boolean {
  return secret() !== null;
}

export function validateTeacherCredential(candidate: string): boolean {
  const configured = secret();
  return configured !== null && safeSecretEqual(candidate, configured);
}

export function createTeacherSession(now = Date.now()): string {
  const configured = secret();
  if (!configured) throw new Error("Teacher UI access is not configured.");
  const issuedAt = Math.floor(now / 1000);
  const payload: SessionPayload = {
    version: 1,
    issuedAt,
    expiresAt: issuedAt + TEACHER_SESSION_SECONDS,
  };
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${encoded}.${signature(encoded, configured)}`;
}

export function verifyTeacherSession(value: string | undefined, now = Date.now()): boolean {
  const configured = secret();
  if (!configured || !value) return false;
  const [encoded, suppliedSignature, ...extra] = value.split(".");
  if (!encoded || !suppliedSignature || extra.length) return false;
  const expectedSignature = signature(encoded, configured);
  if (!safeSecretEqual(suppliedSignature, expectedSignature)) return false;
  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")) as Partial<SessionPayload>;
    const current = Math.floor(now / 1000);
    return payload.version === 1
      && Number.isInteger(payload.issuedAt)
      && Number.isInteger(payload.expiresAt)
      && (payload.issuedAt as number) <= current
      && (payload.expiresAt as number) > current
      && (payload.expiresAt as number) - (payload.issuedAt as number) === TEACHER_SESSION_SECONDS;
  } catch {
    return false;
  }
}

export function readCookie(cookieHeader: string | null, name: string): string | undefined {
  if (!cookieHeader) return undefined;
  for (const item of cookieHeader.split(";")) {
    const [key, ...parts] = item.trim().split("=");
    if (key === name) return decodeURIComponent(parts.join("="));
  }
  return undefined;
}

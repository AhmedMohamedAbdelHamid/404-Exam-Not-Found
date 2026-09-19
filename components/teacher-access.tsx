"use client";

import { type FormEvent, useState } from "react";
import { Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";

export function TeacherAccess({ onUnlock, error, loading }: { onUnlock: (credential: string) => Promise<void>; error: string | null; loading: boolean }) {
  const [credential, setCredential] = useState("");
  const [visible, setVisible] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (credential && !loading) await onUnlock(credential); }
  return (
    <section className="teacher-access" aria-labelledby="teacher-access-title">
      <div className="teacher-access-copy"><div className="eyebrow">SECURE TEACHER WORKSPACE</div><h1 id="teacher-access-title">Class intelligence.<br /><span>Protected by design.</span></h1><p>Unlock durable assessment analytics, topic performance, and confirmed misconception signals.</p><div className="teacher-security-note"><ShieldCheck size={17} aria-hidden /><span>Student answer keys and assessment credentials remain server-side.</span></div></div>
      <form className="premium-panel teacher-access-card" onSubmit={submit} aria-busy={loading}>
        <span className="teacher-lock" aria-hidden><LockKeyhole size={20} /></span><h2>Teacher access</h2><p>Enter your workspace credential to continue.</p>
        <label className="field-label mt-7" htmlFor="teacher-credential">Access credential</label>
        <div className="credential-field"><input id="teacher-credential" className="text-input" type={visible ? "text" : "password"} autoComplete="current-password" value={credential} onChange={(event) => setCredential(event.target.value)} disabled={loading} aria-invalid={Boolean(error)} aria-describedby={error ? "teacher-access-error" : undefined} /><button type="button" onClick={() => setVisible((current) => !current)} aria-label={visible ? "Hide credential" : "Show credential"}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
        {error && <p id="teacher-access-error" className="teacher-access-error" role="alert">{error}</p>}
        <button className="primary-button mt-5 w-full" type="submit" disabled={!credential || loading}>{loading ? "Verifying access…" : "Unlock dashboard"}</button><small>Access expires automatically after eight hours.</small>
      </form>
    </section>
  );
}

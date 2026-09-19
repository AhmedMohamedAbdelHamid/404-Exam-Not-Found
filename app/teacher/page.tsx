"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TeacherAccess } from "@/components/teacher-access";
import { TeacherDashboard } from "@/components/teacher-dashboard";
import { ErrorRecoveryCard } from "@/components/ui";
import { ApiError, teacherApi, type TeacherLive } from "@/lib/api";

type ViewState = "checking" | "locked" | "loading" | "ready" | "error";
const safeMessage = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;

function TeacherLoading() {
  return <div className="premium-panel teacher-loading" aria-busy="true" aria-live="polite"><div className="skeleton h-10 w-10 rounded-xl" /><div className="flex-1"><p>Opening the secure teacher workspace…</p><div className="skeleton mt-3 h-2.5 w-48 max-w-full" /></div></div>;
}

export default function TeacherPage() {
  const initialized = useRef(false);
  const [state, setState] = useState<ViewState>("checking");
  const [data, setData] = useState<TeacherLive | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const loadLive = useCallback(async () => {
    setMessage(null);
    try { setData(await teacherApi.getLive()); setState("ready"); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) { setData(null); setState("locked"); return; }
      setMessage(safeMessage(error, "Live teacher analytics is temporarily unavailable.")); setState("error");
    }
  }, []);
  useEffect(() => { if (!initialized.current) { initialized.current = true; void loadLive(); } }, [loadLive]);
  const unlock = useCallback(async (credential: string) => {
    setState("loading"); setMessage(null);
    try { await teacherApi.unlock(credential); await loadLive(); }
    catch (error) { setData(null); setMessage(safeMessage(error, "Teacher access could not be verified.")); setState("locked"); }
  }, [loadLive]);
  const logout = useCallback(async () => {
    try { await teacherApi.logout(); } finally { setData(null); setMessage(null); setState("locked"); }
  }, []);
  if (state === "checking") return <TeacherLoading />;
  if (state === "locked" || state === "loading") return <TeacherAccess onUnlock={unlock} error={message} loading={state === "loading"} />;
  if (state === "error") return <div className="mx-auto max-w-2xl pt-20"><ErrorRecoveryCard message={message ?? "Live teacher analytics is temporarily unavailable."} onRetry={() => void loadLive()} /><button className="secondary-button mt-4" onClick={() => void logout()}>Return to teacher access</button></div>;
  if (!data) return <TeacherLoading />;
  return <TeacherDashboard data={data} onLogout={() => void logout()} />;
}

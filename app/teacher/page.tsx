"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TeacherDashboard } from "@/components/teacher-dashboard";
import { ErrorRecoveryCard } from "@/components/ui";
import { ApiError, teacherApi, type TeacherLive } from "@/lib/api";

type ViewState = "loading" | "ready" | "error";
const safeMessage = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;

function TeacherLoading() {
  return <div className="premium-panel teacher-loading" aria-busy="true" aria-live="polite"><div className="skeleton h-10 w-10 rounded-xl" /><div className="flex-1"><p>Loading class analytics…</p><div className="skeleton mt-3 h-2.5 w-48 max-w-full" /></div></div>;
}

export default function TeacherPage() {
  const initialized = useRef(false);
  const [state, setState] = useState<ViewState>("loading");
  const [data, setData] = useState<TeacherLive | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const loadLive = useCallback(async () => {
    setMessage(null);
    setState("loading");
    try { setData(await teacherApi.getLive()); setState("ready"); }
    catch (error) {
      setData(null);
      setMessage(safeMessage(error, "Live teacher analytics is temporarily unavailable."));
      setState("error");
    }
  }, []);
  useEffect(() => { if (!initialized.current) { initialized.current = true; void loadLive(); } }, [loadLive]);
  if (state === "loading") return <TeacherLoading />;
  if (state === "error") return <div className="mx-auto max-w-2xl pt-20"><ErrorRecoveryCard message={message ?? "Live teacher analytics is temporarily unavailable."} onRetry={() => void loadLive()} /></div>;
  if (!data) return <TeacherLoading />;
  return <TeacherDashboard data={data} />;
}

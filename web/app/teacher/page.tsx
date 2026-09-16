"use client";

import { useCallback, useEffect, useState } from "react";
import { TeacherDashboard } from "@/components/teacher-dashboard";
import { ErrorRecoveryCard, GenerationLoader } from "@/components/ui";
import { api, ApiError, type TeacherDemo } from "@/lib/api";

export default function TeacherPage() {
  const [data, setData] = useState<TeacherDemo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try { setData(await api.getTeacherDemo()); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "The demo dashboard is unavailable."); }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (error) return <div className="mx-auto max-w-2xl pt-20"><ErrorRecoveryCard message={error} onRetry={load} /></div>;
  if (!data) return <GenerationLoader />;
  return <TeacherDashboard data={data} />;
}

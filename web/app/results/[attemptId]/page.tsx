"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ResultsDashboard } from "@/components/results";
import { ErrorRecoveryCard, GenerationLoader } from "@/components/ui";
import { api, ApiError, type Results } from "@/lib/api";

export default function ResultsPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try { setResults(await api.getResults(attemptId)); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "Results are unavailable right now."); }
  }, [attemptId]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  if (error) return <div className="mx-auto max-w-2xl pt-20"><ErrorRecoveryCard message={error} onRetry={load} /></div>;
  if (!results) return <GenerationLoader />;
  return <ResultsDashboard results={results} />;
}

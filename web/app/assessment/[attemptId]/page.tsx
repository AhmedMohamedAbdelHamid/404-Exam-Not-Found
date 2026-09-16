"use client";

import { useParams, useRouter } from "next/navigation";
import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AssessmentHeader, CompletionHero, QuestionCard } from "@/components/assessment";
import { ErrorRecoveryCard, GenerationLoader } from "@/components/ui";
import { api, ApiError, type Answer, type Attempt, type Question, type Results } from "@/lib/api";
import { copy } from "@/lib/copy";

type Failure = { message: string; retryable: boolean; code: string };
type DeliveryState = "idle" | "loading" | "loaded" | "error";

export default function AssessmentPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [deliveryState, setDeliveryState] = useState<DeliveryState>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const initializedAttemptRef = useRef<string | null>(null);
  const deliveryInFlightRef = useRef(false);

  const normalizeFailure = (caught: unknown): Failure => caught instanceof ApiError
    ? { message: caught.message, retryable: caught.retryable, code: caught.code }
    : { message: "We couldn't complete that request. Please retry.", retryable: true, code: "UNKNOWN" };

  const loadAttempt = useCallback(async () => {
    if (deliveryInFlightRef.current) return;
    deliveryInFlightRef.current = true;
    setDeliveryState("loading"); setFailure(null);
    try {
      let current = await api.getAttempt(attemptId);
      if (current.complete) {
        const report = await api.getResults(attemptId);
        setAttempt(current); setResults(report); setQuestion(null); setAnswer(null);
        setDeliveryState("loaded"); return;
      }
      if (!current.current_question) {
        const next = await api.getNextQuestion(attemptId);
        if (next.complete) {
          current = await api.getAttempt(attemptId);
          const report = await api.getResults(attemptId);
          setAttempt(current); setResults(report); setQuestion(null); setAnswer(null);
          setDeliveryState("loaded"); return;
        }
        current = await api.getAttempt(attemptId);
      }
      setAttempt(current);
      setQuestion(current.current_question);
      setAnswer(current.current_answer);
      setSelected(current.current_answer?.selected_option_id ?? null);
      setDeliveryState("loaded");
    } catch (caught) {
      setFailure(normalizeFailure(caught));
      setDeliveryState("error");
    } finally { deliveryInFlightRef.current = false; }
  }, [attemptId]);

  useEffect(() => {
    if (initializedAttemptRef.current === attemptId) return;
    initializedAttemptRef.current = attemptId;
    // Attempt-scoped idempotency is required because Strict Mode replays effects.
    void loadAttempt();
  }, [attemptId, loadAttempt]);

  async function submit() {
    if (!question || !selected || submitting) return;
    setSubmitting(true); setFailure(null);
    try {
      const saved = await api.submitAnswer(attemptId, question.question_id, selected);
      setAnswer(saved);
      setAttempt((value) => value ? { ...value, current_adaptive_difficulty: saved.current_adaptive_difficulty, progress: saved.progress, answer_state: "saved", current_answer: saved, can_request_next: true } : value);
    } catch (caught) {
      setFailure(normalizeFailure(caught));
    } finally { setSubmitting(false); }
  }

  async function next() {
    if (deliveryInFlightRef.current) return;
    deliveryInFlightRef.current = true;
    setDeliveryState("loading"); setFailure(null);
    try {
      const response = await api.getNextQuestion(attemptId);
      if (response.complete) {
        const [current, report] = await Promise.all([api.getAttempt(attemptId), api.getResults(attemptId)]);
        setAttempt(current); setResults(report); setQuestion(null); setAnswer(null);
      } else {
        const current = await api.getAttempt(attemptId);
        setAttempt(current); setQuestion(response.question); setAnswer(null); setSelected(null);
      }
    } catch (caught) {
      setFailure(normalizeFailure(caught));
      setDeliveryState("error");
      return;
    } finally { deliveryInFlightRef.current = false; }
    setDeliveryState("loaded");
  }

  const loading = deliveryState === "idle" || deliveryState === "loading";
  if (loading && !question && !results) return <GenerationLoader language={attempt?.language} />;
  if (failure && !attempt) return <div className="mx-auto max-w-2xl pt-20"><ErrorRecoveryCard message={failure.message} retryable={failure.retryable} onRetry={loadAttempt} /></div>;
  if (!attempt) return null;
  if (results) return <CompletionHero language={results.language} score={results.summary.score} total={results.summary.attempted} accuracy={results.summary.accuracy} finalLevel={results.summary.final_adaptive_difficulty} onResults={() => router.push(`/results/${attemptId}`)} onRestart={() => { sessionStorage.removeItem("exam-not-found:attempt"); router.push("/"); }} />;

  return (
    <div className="mx-auto max-w-5xl">
      {question && <AssessmentHeader attempt={attempt} question={question} />}
      {failure && <div className="mb-5"><ErrorRecoveryCard message={failure.code === "ANSWER_SYNC_REQUIRED" ? copy[attempt.language].sync : failure.message} retryable={failure.retryable && failure.code !== "ANSWER_SYNC_REQUIRED"} onRetry={failure.code === "ANSWER_SAVE_FAILED" ? submit : next} /></div>}
      <AnimatePresence mode="wait">{loading ? <GenerationLoader key="loader" language={attempt.language} /> : question ? <QuestionCard key={question.question_id} question={question} selected={selected} onSelect={setSelected} answer={answer} submitting={submitting} onSubmit={submit} onContinue={next} /> : null}</AnimatePresence>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, BookOpen, Globe2, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api, ApiError, type Health, type Language } from "@/lib/api";
import { RuntimeStatus } from "@/components/ui";
import { motionTokens } from "@/lib/motion";

export function AssessmentStart() {
  const router = useRouter();
  const reduced = useReducedMotion();
  const [studentId, setStudentId] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth(null)).finally(() => setHealthLoading(false));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const normalized = studentId.trim();
    if (!normalized) {
      setError("Enter a student identifier to begin.");
      return;
    }
    setSubmitting(true); setError(null);
    try {
      const attempt = await api.startAttempt(normalized, language);
      sessionStorage.setItem("exam-not-found:attempt", attempt.attempt_id);
      router.push(`/assessment/${attempt.attempt_id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The assessment could not be started. Please retry.");
      setSubmitting(false);
    }
  }

  return (
    <div className="start-layout grid min-h-[calc(100vh-5rem)] items-center gap-12 py-8 xl:grid-cols-[1.08fr_.92fr] xl:py-0">
      <section className="max-w-3xl">
        <motion.div initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="eyebrow">404 / EXAM NOT FOUND</motion.div>
        <motion.h1 initial={reduced ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .07, duration: reduced ? 0 : motionTokens.page, ease: motionTokens.ease }} className="hero-title">
          Adaptive<br />assessments.<br /><span className="text-zinc-600">Grounded in<br className="hidden sm:block" /> your textbook.</span>
        </motion.h1>
        <motion.p initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .16, duration: reduced ? 0 : motionTokens.page, ease: motionTokens.ease }} className="mt-8 max-w-xl text-base leading-8 text-zinc-400 sm:text-lg">
          A focused assessment that adapts after every answer—without drifting beyond what you actually study.
        </motion.p>
        <motion.div initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reduced ? 0 : .24, duration: motionTokens.card }} className="mt-10 flex flex-wrap gap-5 text-xs text-zinc-500">
          <span className="flex items-center gap-2"><BookOpen size={15} className="text-[#ff6576]" /> Textbook grounded</span>
          <span className="flex items-center gap-2"><ShieldCheck size={15} className="text-[#ff6576]" /> Server-secured answers</span>
          <span className="flex items-center gap-2"><Globe2 size={15} className="text-[#ff6576]" /> English + العربية</span>
        </motion.div>
      </section>

      <motion.section initial={reduced ? false : { opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: reduced ? 0 : .1, duration: reduced ? 0 : .42, ease: motionTokens.ease }} className="premium-panel start-card relative overflow-hidden p-6 sm:p-8">
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-[#ff3045] to-transparent opacity-70" />
        <div className="eyebrow">YOUR ASSESSMENT</div>
        <h2 className="mt-4 text-2xl font-semibold tracking-[-.04em] text-white">Python Fundamentals</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-500">Choose your language track once. Your adaptive path stays consistent for the full attempt.</p>
        <form onSubmit={submit} className="mt-8 space-y-6" noValidate>
          <div>
            <label htmlFor="student-id" className="field-label">Student identifier</label>
            <input id="student-id" value={studentId} onChange={(event) => setStudentId(event.target.value)} maxLength={80} autoComplete="username" placeholder="Enter your student ID" className="text-input" aria-invalid={Boolean(error && !studentId.trim())} />
          </div>
          <fieldset>
            <legend className="field-label">Assessment language</legend>
            <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Assessment language">
              {(["en", "ar"] as Language[]).map((code) => {
                const selected = language === code;
                return (
                  <motion.button key={code} type="button" role="radio" aria-checked={selected} whileHover={reduced ? undefined : { y: -2 }} whileTap={reduced ? undefined : { scale: .988 }} transition={{ duration: motionTokens.micro, ease: motionTokens.ease }} onClick={() => setLanguage(code)} className={`language-card ${selected ? "selected" : ""}`}>
                    <span className="text-sm font-semibold text-zinc-100">{code === "en" ? "English" : "العربية"}</span>
                    <small>{code === "en" ? "English textbook track" : "مسار الكتاب العربي"}</small>
                  </motion.button>
                );
              })}
            </div>
          </fieldset>
          <RuntimeStatus health={health} loading={healthLoading} />
          {error && <p className="rounded-lg border border-red-400/15 bg-red-500/[.07] px-4 py-3 text-sm text-red-200" role="alert">{error}</p>}
          <button disabled={submitting} className="primary-button w-full" type="submit">
            <span>{submitting ? "Opening your assessment…" : "Start assessment"}</span><ArrowRight size={17} aria-hidden />
          </button>
        </form>
      </motion.section>
    </div>
  );
}

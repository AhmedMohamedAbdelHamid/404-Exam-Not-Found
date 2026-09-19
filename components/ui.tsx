"use client";

import { motion, useReducedMotion } from "motion/react";
import { AlertTriangle, Check, RefreshCw, Sparkles } from "lucide-react";
import type { Health, Language } from "@/lib/api";
import { motionTokens } from "@/lib/motion";

export function RuntimeStatus({ health, loading }: { health: Health | null; loading?: boolean }) {
  const configured = health?.status === "configured";
  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/[.07] bg-black/20 p-4" aria-live="polite">
      <span className={`mt-1 size-2 shrink-0 rounded-full ${configured ? "bg-emerald-400 shadow-[0_0_0_5px_rgba(52,211,153,.08)]" : "bg-amber-300 shadow-[0_0_0_5px_rgba(252,211,77,.08)]"}`} />
      <div>
        <p className="text-sm font-medium text-zinc-200">{loading ? "Checking assessment availability…" : configured ? "AI pipeline configured" : "Resilient assessment available"}</p>
        <p className="mt-1 text-xs leading-5 text-zinc-500">Textbook-grounded generation with verified fallback when needed.</p>
      </div>
    </div>
  );
}

export function GenerationLoader({ language = "en" }: { language?: Language }) {
  const reduced = useReducedMotion();
  return (
    <div className="premium-panel mx-auto max-w-4xl p-6 sm:p-8" aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-3 text-sm font-medium text-zinc-200">
        <motion.span animate={reduced ? {} : { rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }} className="grid size-9 place-items-center rounded-full border border-red-400/20 bg-red-500/10 text-[#ff6576]">
          <Sparkles size={16} />
        </motion.span>
        <span>{language === "ar" ? "جارٍ إعداد السؤال التالي…" : "Preparing your next question…"}</span>
      </div>
      <p className="ml-12 mt-1 text-xs text-zinc-600">{language === "ar" ? "جارٍ ربطه بمحتوى كتابك…" : "Grounding it in your textbook…"}</p>
      <div className="mt-8 space-y-3"><div className="skeleton h-5 w-4/5" /><div className="skeleton h-5 w-2/3" /><div className="mt-7 grid gap-3"><div className="skeleton h-14" /><div className="skeleton h-14" /><div className="skeleton h-14" /></div></div>
    </div>
  );
}

export function ErrorRecoveryCard({ message, onRetry, retryable = true }: { message: string; onRetry?: () => void; retryable?: boolean }) {
  return (
    <div className="rounded-2xl border border-red-400/15 bg-red-500/[.06] p-5" role="alert">
      <div className="flex gap-3"><AlertTriangle className="mt-0.5 shrink-0 text-[#ff6576]" size={18} /><div><h3 className="text-sm font-semibold text-zinc-100">We hit a temporary interruption</h3><p className="mt-1 text-sm leading-6 text-zinc-400">{message}</p></div></div>
      {retryable && onRetry && <button className="secondary-button mt-4" onClick={onRetry}><RefreshCw size={15} /> Retry</button>}
    </div>
  );
}

export function CheckBadge({ correct }: { correct: boolean }) {
  return correct ? <span className="grid size-8 place-items-center rounded-full bg-emerald-400/12 text-emerald-300"><Check size={17} /></span> : <span className="grid size-8 place-items-center rounded-full bg-red-400/12 text-[#ff8794]"><AlertTriangle size={16} /></span>;
}

export function MetricCard({ label, value, note, index = 0 }: { label: string; value: string; note: string; index?: number }) {
  const reduced = useReducedMotion();
  return (
    <motion.article className="metric-card" initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} whileHover={reduced ? undefined : { y: -3 }} transition={{ delay: reduced ? 0 : index * 0.05, duration: reduced ? 0 : motionTokens.card, ease: motionTokens.ease }}>
      <p>{label}</p><strong>{value}</strong><small>{note}</small>
    </motion.article>
  );
}

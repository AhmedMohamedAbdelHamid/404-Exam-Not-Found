"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight, Check, RotateCcw } from "lucide-react";
import { KeyboardEvent, useRef } from "react";
import { copy } from "@/lib/copy";
import type { Answer, Attempt, Language, Question } from "@/lib/api";
import { MixedText } from "@/components/mixed-text";
import { CheckBadge } from "@/components/ui";
import { motionTokens } from "@/lib/motion";
import { formatTopicName } from "@/lib/presentation";

export function AdaptiveLevel({ level, language }: { level: number; language: Language }) {
  const reduced = useReducedMotion();
  return (
    <div className="adaptive-level" aria-label={`${copy[language].adaptive} ${level} of 5`}>
      <div className="flex items-baseline justify-between gap-4"><span>{copy[language].adaptive}</span><AnimatePresence mode="popLayout" initial={false}><motion.strong key={level} aria-live="polite" initial={reduced ? false : { y: level > 3 ? 7 : -7, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={reduced ? undefined : { y: -5, opacity: 0 }} transition={reduced ? { duration: 0 } : motionTokens.spring}>{level}<small>/5</small></motion.strong></AnimatePresence></div>
      <div className="mt-3 flex gap-1.5" aria-hidden>{[1, 2, 3, 4, 5].map((item) => <motion.i key={item} animate={{ backgroundColor: item <= level ? "#ff3045" : "#27272a", scaleX: item <= level ? 1 : .82, opacity: item <= level ? 1 : .62 }} transition={reduced ? { duration: 0 } : motionTokens.spring} />)}</div>
    </div>
  );
}

export function AssessmentHeader({ attempt, question }: { attempt: Attempt; question: Question }) {
  const reduced = useReducedMotion();
  const labels = copy[attempt.language];
  const percent = Math.min(100, ((question.question_number - 1) / attempt.progress.total) * 100);
  return (
    <header className="mb-6">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div dir={attempt.language === "ar" ? "rtl" : "ltr"}>
          <div className="eyebrow">PYTHON FUNDAMENTALS</div>
          <h1 className="assessment-question-number">{labels.question} <span>{String(question.question_number).padStart(2, "0")}</span> <small>/ {String(attempt.progress.total).padStart(2, "0")}</small></h1>
        </div>
        <AdaptiveLevel level={attempt.current_adaptive_difficulty} language={attempt.language} />
      </div>
      <div className="mt-7 h-1 overflow-hidden rounded-full bg-white/[.06]" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <motion.div className="h-full rounded-full bg-gradient-to-r from-red-900 via-[#ff3045] to-[#ff6576]" initial={false} animate={{ width: `${percent}%` }} transition={{ duration: reduced ? 0 : .42, ease: motionTokens.ease }} />
      </div>
    </header>
  );
}

type QuestionCardProps = {
  question: Question;
  selected: string | null;
  onSelect: (id: string) => void;
  answer: Answer | null;
  submitting: boolean;
  onSubmit: () => void;
  onContinue: () => void;
};

export function QuestionCard({ question, selected, onSelect, answer, submitting, onSubmit, onContinue }: QuestionCardProps) {
  const reduced = useReducedMotion();
  const labels = copy[question.language];
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const locked = Boolean(answer);

  function keyboardSelect(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (locked || !["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
    const next = (index + direction + question.options.length) % question.options.length;
    onSelect(question.options[next].id);
    optionRefs.current[next]?.focus();
  }

  return (
    <motion.article key={question.question_id} initial={reduced ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={reduced ? { opacity: 0 } : { opacity: 0, y: -10 }} transition={{ duration: reduced ? 0 : motionTokens.page, ease: motionTokens.ease }} className="question-panel" dir={question.language === "ar" ? "rtl" : "ltr"}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="meta-chip accent">PYTHON FUNDAMENTALS</span><span className="meta-chip" dir="ltr">{formatTopicName(question.topic)}</span><span className="meta-chip">{question.language === "ar" ? "العربية" : "English"}</span>
        {question.source === "fallback" && <span className="meta-chip fallback">{labels.fallback}</span>}
      </div>
      <h2 className="question-copy"><MixedText text={question.question} language={question.language} /></h2>
      <p className="mt-3 text-sm text-zinc-600">{labels.choose}</p>
      <div className="mt-8 grid gap-3" role="radiogroup" aria-label={labels.choose}>
        {question.options.map((option, index) => {
          const isSelected = selected === option.id;
          const isCorrect = answer?.correct_option_id === option.id;
          const isWrongSelection = Boolean(answer && answer.selected_option_id === option.id && !answer.correct);
          return (
            <motion.button
              ref={(node) => { optionRefs.current[index] = node; }}
              key={option.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={locked}
              tabIndex={isSelected || (!selected && index === 0) ? 0 : -1}
              onKeyDown={(event) => keyboardSelect(event, index)}
              onClick={() => onSelect(option.id)}
              whileHover={locked || reduced ? undefined : { y: -2 }}
              whileTap={locked || reduced ? undefined : { scale: .994 }}
              transition={{ duration: motionTokens.micro, ease: motionTokens.ease }}
              animate={{ borderColor: isCorrect ? "rgba(52,211,153,.46)" : isWrongSelection ? "rgba(255,48,69,.52)" : isSelected ? "rgba(255,48,69,.62)" : "rgba(255,255,255,.075)" }}
              className={`option-card ${isSelected ? "selected" : ""} ${isCorrect ? "correct" : ""} ${isWrongSelection ? "incorrect" : ""}`}
            >
              <span className="option-label">{option.label}</span><MixedText text={option.text} language={question.language} className="min-w-0 flex-1" />
              {isCorrect && <Check size={17} className="shrink-0 text-emerald-300" aria-label={labels.correct} />}
            </motion.button>
          );
        })}
      </div>

      <AnimatePresence>
        {answer && (
          <motion.div initial={reduced ? false : { opacity: 0, height: 0, y: 6 }} animate={{ opacity: 1, height: "auto", y: 0 }} transition={{ duration: reduced ? 0 : motionTokens.card, ease: motionTokens.ease }} className={`feedback-panel ${answer.correct ? "correct" : "incorrect"}`} aria-live="polite">
            <CheckBadge correct={answer.correct} />
            <div><h3>{answer.correct ? labels.correct : labels.incorrect}</h3>{!answer.correct && <p><strong>{labels.correctAnswer}:</strong> <MixedText text={answer.correct_answer} language={question.language} /></p>}{answer.misconception && <small><strong>{labels.learningSignal}:</strong> <MixedText text={answer.misconception} language={question.language} /></small>}</div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="mt-8 flex flex-col-reverse items-stretch justify-between gap-4 border-t border-white/[.06] pt-6 sm:flex-row sm:items-center">
        <p className="text-center text-xs text-zinc-600 sm:text-start">{question.source === "fallback" ? labels.fallback : labels.grounded}</p>
        {!answer ? (
          <button className="primary-button min-w-48" disabled={!selected || submitting} onClick={onSubmit}>{submitting ? "Saving…" : labels.submit}<ArrowRight size={17} /></button>
        ) : (
          <button className="primary-button min-w-48" onClick={onContinue}>{answer.can_continue ? labels.next : labels.finish}<ArrowRight size={17} /></button>
        )}
      </div>
    </motion.article>
  );
}

export function CompletionHero({ language, score, total, accuracy, finalLevel, onResults, onRestart }: { language: Language; score: number; total: number; accuracy: number; finalLevel: number; onResults: () => void; onRestart: () => void }) {
  const reduced = useReducedMotion(); const labels = copy[language];
  return (
    <motion.section initial={reduced ? false : { opacity: 0, scale: .985 }} animate={{ opacity: 1, scale: 1 }} className="premium-panel mx-auto max-w-4xl overflow-hidden p-7 text-center sm:p-12" dir={language === "ar" ? "rtl" : "ltr"}>
      <div className="eyebrow">{labels.complete}</div><h1 className="mt-5 text-4xl font-semibold tracking-[-.055em] text-white sm:text-5xl">{labels.complete}</h1>
      <div className="completion-stats mx-auto mt-9 grid max-w-xl grid-cols-3 divide-x divide-white/[.07] rounded-2xl border border-white/[.07] bg-black/25 py-6">
        <div><strong className="completion-value">{score}<small>/{total}</small></strong><span>{labels.score}</span></div>
        <div><strong className="completion-value">{accuracy}<small>%</small></strong><span>{labels.accuracy}</span></div>
        <div><strong className="completion-value">{finalLevel}<small>/5</small></strong><span>{labels.finalLevel}</span></div>
      </div>
      <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row"><button className="primary-button" onClick={onResults}>{labels.viewResults}<ArrowRight size={17} /></button><button className="secondary-button" onClick={onRestart}><RotateCcw size={16} />{labels.newAttempt}</button></div>
    </motion.section>
  );
}

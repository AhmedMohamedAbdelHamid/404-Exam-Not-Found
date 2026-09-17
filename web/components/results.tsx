"use client";

import * as Accordion from "@radix-ui/react-accordion";
import { motion, useReducedMotion } from "motion/react";
import { CheckCircle2, ChevronDown, Lightbulb, XCircle } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Language, Results } from "@/lib/api";
import { MixedText } from "@/components/mixed-text";
import { MetricCard } from "@/components/ui";
import { motionTokens } from "@/lib/motion";
import { accuracyTieCount, formatTopicName } from "@/lib/presentation";

const labels = {
  en: {
    complete: "Assessment complete", subtitle: "A focused view of this completed adaptive session.", session: "REAL SESSION DATA",
    score: "Score", accuracy: "Accuracy", correct: "Correct", incorrect: "Incorrect", average: "Average difficulty",
    topic: "Performance by topic", topicSub: "Accuracy across each assessed curriculum area", journey: "Adaptive journey",
    journeySub: "Difficulty after each submitted answer", strongest: "Strongest topic", strongestTie: "One of your strongest topics",
    attention: "Needs attention", attentionTie: "Lowest-performing topic · tie resolved alphabetically",
    misconceptions: "Misconceptions detected", misconceptionSub: "Learning signals from incorrect selections only",
    review: "Question review", reviewSub: "Your submitted answer compared with the correct answer",
    yourAnswer: "Your answer", correctAnswer: "Correct answer", difficulty: "Difficulty", noMisconceptions: "No misconceptions were detected.",
    initial: "Initial level", afterQuestion: "After question", level: "Adaptive level", question: "Question",
  },
  ar: {
    complete: "اكتمل التقييم", subtitle: "عرض مركز لنتائج جلسة التقييم التكيفية المكتملة.", session: "بيانات الجلسة الفعلية",
    score: "النتيجة", accuracy: "الدقة", correct: "إجابة صحيحة", incorrect: "إجابة غير صحيحة", average: "متوسط الصعوبة",
    topic: "الأداء حسب الموضوع", topicSub: "الدقة في كل مجال من مجالات المنهج", journey: "المسار التكيفي",
    journeySub: "مستوى الصعوبة بعد كل إجابة", strongest: "أقوى موضوع", strongestTie: "أحد أقوى موضوعاتك",
    attention: "يحتاج إلى اهتمام", attentionTie: "أقل موضوع أداءً · حُسم التعادل أبجديًا",
    misconceptions: "المفاهيم الخاطئة المكتشفة", misconceptionSub: "إشارات التعلم من الاختيارات الخاطئة فقط",
    review: "مراجعة الأسئلة", reviewSub: "إجابتك المرسلة مقارنة بالإجابة الصحيحة",
    yourAnswer: "إجابتك", correctAnswer: "الإجابة الصحيحة", difficulty: "الصعوبة", noMisconceptions: "لم تُكتشف مفاهيم خاطئة.",
    initial: "المستوى الأولي", afterQuestion: "بعد السؤال", level: "المستوى التكيفي", question: "السؤال",
  },
} as const;

function SectionTitle({ title, subtitle, language }: { title: string; subtitle: string; language: Language }) {
  return <div className="mb-6" dir={language === "ar" ? "rtl" : "ltr"}><h2 className="text-lg font-semibold tracking-[-.03em] text-white">{title}</h2><p className="mt-1.5 text-xs leading-5 text-zinc-500">{subtitle}</p></div>;
}

export function ScoreHero({ results }: { results: Results }) {
  const reduced = useReducedMotion(); const t = labels[results.language]; const { summary } = results;
  return (
    <motion.section initial={reduced ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduced ? 0 : motionTokens.page, ease: motionTokens.ease }} className="score-hero" dir={results.language === "ar" ? "rtl" : "ltr"}>
      <motion.div initial={reduced ? false : { rotate: -8, scale: .94 }} animate={{ rotate: 0, scale: 1 }} transition={reduced ? { duration: 0 } : motionTokens.spring} className="score-ring" style={{ background: `conic-gradient(#ff3045 ${summary.accuracy}%, #242429 0)` }} aria-label={`${summary.accuracy}% ${t.accuracy}`}><div><motion.strong initial={reduced ? false : { opacity: 0, scale: .8 }} animate={{ opacity: 1, scale: 1 }}>{summary.accuracy}<small>%</small></motion.strong><span>{t.accuracy}</span></div></motion.div>
      <div className="min-w-0 flex-1"><div className="eyebrow">{t.session}</div><h1 className="mt-3 text-3xl font-semibold tracking-[-.05em] text-white sm:text-4xl">{t.complete}</h1><p className="mt-2 text-sm text-zinc-400">{t.subtitle}</p><div className="mt-5 text-3xl font-semibold text-white">{summary.score} <small className="text-lg font-normal text-zinc-500">/ {summary.attempted}</small></div></div>
      <span className="meta-chip accent self-start">{results.student_id}</span>
    </motion.section>
  );
}

export function ResultsDashboard({ results }: { results: Results }) {
  const reduced = useReducedMotion(); const t = labels[results.language]; const rtl = results.language === "ar";
  const strongestTies = accuracyTieCount(results.topics, "highest");
  const attentionTies = accuracyTieCount(results.topics, "lowest");
  const metrics = [
    [t.score, `${results.summary.score} / ${results.summary.attempted}`, rtl ? "الإجابات الصحيحة / المحاولات" : "Correct answers / attempted"],
    [t.accuracy, `${results.summary.accuracy}%`, rtl ? "الأداء العام" : "Overall performance"],
    [t.correct, String(results.summary.correct), rtl ? "الإجابات المرسلة" : "Submitted answers"],
    [t.incorrect, String(results.summary.incorrect), rtl ? "الإجابات المرسلة" : "Submitted answers"],
    [t.average, `${results.summary.average_question_difficulty} / 5`, rtl ? "عبر الأسئلة المجابة" : "Across answered questions"],
  ];
  return (
    <div className="space-y-6">
      <ScoreHero results={results} />
      <div className="metrics-grid grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{metrics.map(([label, value, note], index) => <MetricCard key={label} label={label} value={value} note={note} index={index} />)}</div>
      <div className="grid min-w-0 gap-6 xl:grid-cols-[1.15fr_.85fr]">
        <section className="premium-panel min-w-0 p-5 sm:p-6"><SectionTitle title={t.topic} subtitle={t.topicSub} language={results.language} /><div className="space-y-5">{results.topics.map((topic, index) => <motion.div key={topic.topic} initial={reduced ? false : { opacity: 0, x: rtl ? 10 : -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: reduced ? 0 : index * .05, duration: motionTokens.card }}><div className="mb-2.5 flex items-end justify-between gap-3"><div className="min-w-0"><strong className="text-sm font-medium text-zinc-100"><bdi dir="auto">{formatTopicName(topic.topic)}</bdi></strong><p className="mt-1 text-[11px] text-zinc-500">{topic.correct} {t.correct.toLocaleLowerCase()} · {topic.incorrect} {t.incorrect.toLocaleLowerCase()}</p></div><span className="shrink-0 text-sm font-semibold text-[#ff6576]">{topic.accuracy}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-white/[.06]"><motion.div className="h-full rounded-full bg-gradient-to-r from-red-900 to-[#ff3045]" initial={{ width: 0 }} animate={{ width: `${topic.accuracy}%` }} transition={{ delay: reduced ? 0 : .14 + index * .05, duration: reduced ? 0 : .45, ease: motionTokens.ease }} /></div></motion.div>)}</div></section>
        <section className="premium-panel min-h-[330px] min-w-0 p-5 sm:p-6"><SectionTitle title={t.journey} subtitle={t.journeySub} language={results.language} /><div className="h-[245px] min-w-0" role="img" aria-label={t.journey}><ResponsiveContainer width="100%" height="100%"><LineChart data={results.adaptive_journey} margin={{ top: 12, right: 12, left: -18, bottom: 8 }}><CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} /><XAxis dataKey="step" stroke="#71717a" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} tickFormatter={(step) => Number(step) === 0 ? (rtl ? "بدء" : "Start") : `${rtl ? "س" : "Q"}${step}`} /><YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} allowDecimals={false} stroke="#71717a" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><Tooltip cursor={{ stroke: "rgba(255,255,255,.1)", strokeDasharray: "3 3" }} contentStyle={{ background: "#121216", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, boxShadow: "0 16px 40px rgba(0,0,0,.35)", fontSize: 12 }} labelStyle={{ color: "#a1a1aa", marginBottom: 4 }} labelFormatter={(step) => Number(step) === 0 ? t.initial : `${t.afterQuestion} ${step}`} formatter={(value) => [`${value} / 5`, t.level]} /><Line type="stepAfter" dataKey="difficulty" stroke="#ff3045" strokeWidth={2.5} dot={{ fill: "#09090b", stroke: "#ff6576", strokeWidth: 2, r: 4 }} activeDot={{ r: 5, fill: "#ff3045", stroke: "#fff", strokeWidth: 1 }} animationDuration={reduced ? 0 : 450} isAnimationActive={!reduced} /></LineChart></ResponsiveContainer><p className="sr-only">{results.adaptive_journey.map((point) => `${point.step === 0 ? t.initial : `${t.afterQuestion} ${point.step}`}: ${point.difficulty} / 5`).join("; ")}</p></div></section>
      </div>
      <div className="grid gap-4 sm:grid-cols-2"><article className="insight-card"><span>01</span><div><p>{strongestTies > 1 ? t.strongestTie : t.strongest}</p><strong><bdi dir="auto">{results.strongest_topic ? formatTopicName(results.strongest_topic) : "—"}</bdi></strong></div></article><article className="insight-card attention"><span>02</span><div><p>{attentionTies > 1 ? t.attentionTie : t.attention}</p><strong><bdi dir="auto">{results.needs_attention_topic ? formatTopicName(results.needs_attention_topic) : "—"}</bdi></strong></div></article></div>
      <section className="premium-panel p-5 sm:p-6"><SectionTitle title={t.misconceptions} subtitle={t.misconceptionSub} language={results.language} />{results.misconceptions.length ? <div className="grid gap-3 md:grid-cols-2">{results.misconceptions.map((item, index) => <motion.article key={item.misconception} initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : index * .05, duration: motionTokens.card }} className="misconception-card"><Lightbulb size={17} /><div className="min-w-0"><MixedText text={item.misconception} language={results.language} className="text-sm text-zinc-100" /><p>{item.topics.map(formatTopicName).join(", ")} · {item.occurrences}×</p></div></motion.article>)}</div> : <p className="text-sm text-zinc-400">{t.noMisconceptions}</p>}</section>
      <section><SectionTitle title={t.review} subtitle={t.reviewSub} language={results.language} /><Accordion.Root type="multiple" className="space-y-3">{results.question_review.map((review) => <Accordion.Item key={review.question_id} value={review.question_id} className="review-item"><Accordion.Header><Accordion.Trigger className="review-trigger" aria-label={`${t.question} ${review.question_number}, ${review.correct ? t.correct : t.incorrect}`}><span className="review-number">{String(review.question_number).padStart(2, "0")}</span><span className="min-w-0 flex-1 text-start"><span className="review-topic"><bdi dir="auto">{formatTopicName(review.topic)}</bdi></span><span className="review-difficulty">{t.difficulty} {review.difficulty} / 5</span></span><span className={`review-status ${review.correct ? "correct" : "incorrect"}`}>{review.correct ? <CheckCircle2 size={15} /> : <XCircle size={15} />}{review.correct ? t.correct : t.incorrect}</span><ChevronDown className="chevron" size={17} /></Accordion.Trigger></Accordion.Header><Accordion.Content className="review-content" dir={review.language === "ar" ? "rtl" : "ltr"}><div className="review-question"><MixedText text={review.question} language={review.language} /></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className={`review-answer ${review.correct ? "selected-correct" : "selected-wrong"}`}><small>{t.yourAnswer}</small><MixedText text={review.selected_answer} language={review.language} /></div><div className="review-answer correct"><small>{t.correctAnswer}</small><MixedText text={review.correct_answer} language={review.language} /></div>{review.misconception && <div className="review-answer misconception sm:col-span-2"><small>{t.misconceptions}</small><MixedText text={review.misconception} language={review.language} /></div>}</div></Accordion.Content></Accordion.Item>)}</Accordion.Root></section>
    </div>
  );
}

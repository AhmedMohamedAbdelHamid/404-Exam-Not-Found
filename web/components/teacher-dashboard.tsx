"use client";

import { motion, useReducedMotion } from "motion/react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TeacherDemo } from "@/lib/api";
import { MetricCard } from "@/components/ui";
import { motionTokens } from "@/lib/motion";
import { formatTopicName, summarizeSignal } from "@/lib/presentation";

const numberValue = (value: unknown) => typeof value === "number" ? value : 0;
const stringValue = (value: unknown) => typeof value === "string" ? value : "—";

type RankedItem = { label: string; fullLabel: string; value: number; suffix: string };

function ChartHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return <div><h2 className="text-base font-semibold tracking-[-.02em] text-white">{title}</h2><p className="mt-1.5 text-xs leading-5 text-zinc-500">{subtitle}</p></div>;
}

function RankedBars({ items, label }: { items: RankedItem[]; label: string }) {
  const reduced = useReducedMotion();
  const maximum = Math.max(1, ...items.map((item) => item.value));
  return (
    <div className="ranked-bars" role="list" aria-label={label}>
      {items.map((item, index) => (
        <div className="ranked-row" role="listitem" key={`${item.fullLabel}-${index}`}>
          <span className="ranked-number" aria-hidden>{String(index + 1).padStart(2, "0")}</span>
          <div className="min-w-0 flex-1">
            <div className="ranked-copy"><span title={item.fullLabel}>{item.label}</span><strong>{item.value}{item.suffix}</strong></div>
            <div className="ranked-track" aria-hidden><motion.i initial={{ width: 0 }} animate={{ width: `${(item.value / maximum) * 100}%` }} transition={{ duration: reduced ? 0 : .42, delay: reduced ? 0 : index * .05, ease: motionTokens.ease }} /></div>
            {item.label !== item.fullLabel && <span className="sr-only">Full description: {item.fullLabel}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TeacherDashboard({ data }: { data: TeacherDemo }) {
  const reduced = useReducedMotion(); const summary = data.summary;
  const metrics = [
    ["Students", String(numberValue(summary.students)), "Deterministic demo roster"],
    ["Completion", `${numberValue(summary.completion_rate)}%`, `${numberValue(summary.completed_assessments)} completed`],
    ["Average accuracy", `${numberValue(summary.average_accuracy)}%`, "Completed students only"],
    ["Average score", `${numberValue(summary.average_correct)} / ${numberValue(summary.average_total)}`, "Completed assessments"],
    ["Misconceptions", String(numberValue(summary.distinct_misconceptions)), "Distinct learning signals"],
    ["Avg. difficulty", `${numberValue(summary.average_difficulty)} / 5`, "Across demo responses"],
  ];
  const scores = data.score_distribution.map((row) => ({ band: stringValue(row.band), students: numberValue(row.students) }));
  const topics: RankedItem[] = data.topics.map((row) => {
    const topic = formatTopicName(stringValue(row.topic));
    return { label: topic, fullLabel: topic, value: numberValue(row.error_rate), suffix: "%" };
  });
  const misconceptionSignals: RankedItem[] = data.misconceptions.slice(0, 5).map((row) => {
    const fullLabel = stringValue(row.label);
    return { label: summarizeSignal(fullLabel), fullLabel, value: numberValue(row.occurrences), suffix: "×" };
  });
  const difficultyByLevel = new Map(data.difficulty.map((row) => [numberValue(row.difficulty), numberValue(row.count)]));
  const difficulty = [1, 2, 3, 4, 5].map((level) => ({ difficulty: `L${level}`, count: difficultyByLevel.get(level) ?? 0 }));

  return (
    <div className="space-y-6">
      <header className="teacher-heading"><div><div className="eyebrow">TEACHER WORKSPACE</div><h1 className="mt-3 text-4xl font-semibold tracking-[-.055em] text-white">Class intelligence</h1><p className="mt-2 text-sm text-zinc-400">A deterministic preview built for instructional decisions.</p></div><span className="demo-badge">{data.label}</span></header>
      <div className="teacher-kpis grid gap-3 sm:grid-cols-2 xl:grid-cols-6">{metrics.map(([label, value, note], index) => <MetricCard key={label} label={label} value={value} note={note} index={index} />)}</div>
      <div className="grid min-w-0 gap-6 xl:grid-cols-2">
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: motionTokens.card }} className="premium-panel min-w-0 p-5 sm:p-6" aria-labelledby="class-performance-title"><div id="class-performance-title"><ChartHeader title="Class performance" subtitle="Completed students by score band" /></div><div className="mt-5 h-64" role="img" aria-label="Class performance by score band"><ResponsiveContainer width="100%" height="100%"><BarChart data={scores} margin={{ left: -20, right: 8, bottom: 8 }}><CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} /><XAxis dataKey="band" tick={{ fill: "#a1a1aa", fontSize: 10 }} axisLine={false} tickLine={false} interval={0} /><YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: "rgba(255,255,255,.025)" }} contentStyle={{ background: "#121216", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, boxShadow: "0 16px 40px rgba(0,0,0,.35)", fontSize: 12 }} formatter={(value) => [value, "Students"]} /><Bar dataKey="students" fill="#ff3045" radius={[5, 5, 1, 1]} animationDuration={reduced ? 0 : 420} isAnimationActive={!reduced} /></BarChart></ResponsiveContainer></div></motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .06, duration: motionTokens.card }} className="premium-panel p-5 sm:p-6"><ChartHeader title="Weakest topics" subtitle="Error rate by curriculum area" /><RankedBars items={topics} label="Topics ranked by error rate" /></motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .12, duration: motionTokens.card }} className="premium-panel p-5 sm:p-6"><ChartHeader title="Misconception signals" subtitle="Most frequent incorrect-answer patterns" /><RankedBars items={misconceptionSignals} label="Misconceptions ranked by occurrence" /><details className="signal-details"><summary>Full signal descriptions</summary><ol>{misconceptionSignals.map((item, index) => <li key={item.fullLabel}><span>{String(index + 1).padStart(2, "0")}</span>{item.fullLabel}</li>)}</ol></details></motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .18, duration: motionTokens.card }} className="premium-panel min-w-0 p-5 sm:p-6"><ChartHeader title="Difficulty distribution" subtitle="Question volume at every adaptive level" /><div className="mt-5 h-64" role="img" aria-label="Question difficulty distribution from level one to five"><ResponsiveContainer width="100%" height="100%"><BarChart data={difficulty} margin={{ left: -20, right: 8, bottom: 8 }}><CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} /><XAxis dataKey="difficulty" tick={{ fill: "#a1a1aa", fontSize: 10 }} axisLine={false} tickLine={false} interval={0} /><YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: "rgba(255,255,255,.025)" }} contentStyle={{ background: "#121216", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, boxShadow: "0 16px 40px rgba(0,0,0,.35)", fontSize: 12 }} formatter={(value) => [value, "Questions"]} /><Bar dataKey="count" fill="#ff3045" radius={[5, 5, 1, 1]} animationDuration={reduced ? 0 : 420} isAnimationActive={!reduced} /></BarChart></ResponsiveContainer></div><div className="difficulty-scale" aria-hidden>{[1, 2, 3, 4, 5].map((level) => <span key={level}>Level {level}</span>)}</div></motion.section>
      </div>
      <section className="premium-panel overflow-hidden"><div className="table-heading"><div><h2 className="text-base font-semibold text-white">Student performance</h2><p className="mt-1.5 text-xs text-zinc-500">Demo session outcomes · not live student records</p></div><span className="table-scroll-hint">Scroll to review all metrics →</span></div><div className="student-table-wrap" role="region" aria-label="Student performance table" tabIndex={0}><table className="student-table"><thead><tr><th>Student</th><th>Status</th><th>Score</th><th>Accuracy</th><th>Correct</th><th>Incorrect</th><th>Focus topic</th></tr></thead><tbody>{data.students.map((student) => <tr key={stringValue(student.student_id)}><td className="student-name">{stringValue(student.student)}</td><td><span className={`table-status ${student.completed ? "complete" : "incomplete"}`}>{student.completed ? "Completed" : "In progress"}</span></td><td className="numeric-cell">{stringValue(student.score)}</td><td className="numeric-cell">{numberValue(student.accuracy)}%</td><td className="numeric-cell">{numberValue(student.correct)}</td><td className="numeric-cell">{numberValue(student.incorrect)}</td><td className="focus-topic">{formatTopicName(stringValue(student.main_weak_topic))}</td></tr>)}</tbody></table></div></section>
    </div>
  );
}

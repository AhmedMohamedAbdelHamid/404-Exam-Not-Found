"use client";

import { motion, useReducedMotion } from "motion/react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Database, LogOut } from "lucide-react";
import type { Language, TeacherLive } from "@/lib/api";
import { MetricCard } from "@/components/ui";
import { MixedText } from "@/components/mixed-text";
import { motionTokens } from "@/lib/motion";
import { formatTopicName, summarizeSignal } from "@/lib/presentation";

type RankedItem = { label: string; fullLabel: string; value: number; suffix: string };

function displayTopic(topic: string): string {
  return /[\u0600-\u06ff]/.test(topic) ? topic : formatTopicName(topic);
}

function textLanguage(text: string): Language {
  return /[\u0600-\u06ff]/.test(text) ? "ar" : "en";
}

function ChartHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return <div><h2 className="text-base font-semibold tracking-[-.02em] text-white">{title}</h2><p className="mt-1.5 text-xs leading-5 text-zinc-500">{subtitle}</p></div>;
}

function RankedBars({ items, label }: { items: RankedItem[]; label: string }) {
  const reduced = useReducedMotion();
  const maximum = Math.max(1, ...items.map((item) => item.value));
  if (!items.length) return <p className="mt-6 text-sm text-zinc-500">No confirmed signals yet.</p>;
  return (
    <div className="ranked-bars" role="list" aria-label={label}>
      {items.map((item, index) => (
        <div className="ranked-row" role="listitem" key={`${item.fullLabel}-${index}`}>
          <span className="ranked-number" aria-hidden>{String(index + 1).padStart(2, "0")}</span>
          <div className="min-w-0 flex-1">
            <div className="ranked-copy">
              <span title={item.fullLabel}><MixedText text={item.label} language={textLanguage(item.fullLabel)} /></span>
              <strong>{item.value}{item.suffix}</strong>
            </div>
            <div className="ranked-track" aria-hidden><motion.i initial={{ width: 0 }} animate={{ width: `${(item.value / maximum) * 100}%` }} transition={{ duration: reduced ? 0 : .42, delay: reduced ? 0 : index * .05, ease: motionTokens.ease }} /></div>
            {item.label !== item.fullLabel && <span className="sr-only">Full description: {item.fullLabel}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function TeacherHeader({ onLogout }: { onLogout: () => void }) {
  return (
    <header className="teacher-heading">
      <div><div className="eyebrow">TEACHER WORKSPACE</div><h1 className="mt-3 text-4xl font-semibold tracking-[-.055em] text-white">Class intelligence</h1><p className="mt-2 text-sm text-zinc-400">Durable assessment signals for informed instruction.</p></div>
      <div className="flex flex-wrap items-center gap-2"><span className="live-badge"><i aria-hidden /> LIVE CLASS DATA</span><button type="button" className="secondary-button" onClick={onLogout}><LogOut size={14} aria-hidden /> Log out</button></div>
    </header>
  );
}

function EmptyDashboard({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="space-y-6">
      <TeacherHeader onLogout={onLogout} />
      <section className="teacher-empty premium-panel" aria-labelledby="teacher-empty-title"><span className="teacher-empty-icon" aria-hidden><Database size={24} /></span><div><p className="eyebrow">LIVE CONNECTION READY</p><h2 id="teacher-empty-title">Your class analytics will appear here.</h2><p>This dashboard is connected to durable assessment data. There are no persisted student attempts yet; metrics will populate as students begin and complete assessments.</p></div></section>
    </div>
  );
}

export function TeacherDashboard({ data, onLogout }: { data: TeacherLive; onLogout: () => void }) {
  const reduced = useReducedMotion();
  if (data.data_status === "empty") return <EmptyDashboard onLogout={onLogout} />;
  const { summary } = data;
  const metrics = [
    ["Students", String(summary.total_students), `${summary.total_attempts} total attempts`],
    ["Attempts", String(summary.total_attempts), `${summary.in_progress_attempts} currently in progress`],
    ["Completion", `${summary.completion_rate}%`, `${summary.completed_attempts} completed`],
    ["Overall accuracy", `${summary.overall_accuracy}%`, `${summary.confirmed_answers} confirmed answers`],
    ["Average score", String(summary.average_score), "Correct answers per completed attempt"],
    ["Avg. difficulty", `${summary.average_difficulty} / 5`, "Actual question difficulty"],
    ["Misconceptions", String(summary.misconception_count), "Confirmed incorrect-answer signals"],
  ];
  const scores = data.score_distribution.map((row) => ({ band: row.band, attempts: row.attempts }));
  const topics: RankedItem[] = data.topics.map((row) => ({ label: displayTopic(row.topic), fullLabel: displayTopic(row.topic), value: row.accuracy, suffix: "%" }));
  const misconceptionSignals: RankedItem[] = data.misconceptions.map((row) => ({ label: summarizeSignal(row.misconception), fullLabel: row.misconception, value: row.count, suffix: "×" }));
  const difficultyByLevel = new Map(data.difficulty.map((row) => [row.difficulty, row.count]));
  const difficulty = [1, 2, 3, 4, 5].map((level) => ({ difficulty: `L${level}`, count: difficultyByLevel.get(level) ?? 0 }));

  return (
    <div className="space-y-6">
      <TeacherHeader onLogout={onLogout} />
      <div className="teacher-kpis grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">{metrics.map(([label, value, note], index) => <MetricCard key={label} label={label} value={value} note={note} index={index} />)}</div>
      <div className="grid min-w-0 gap-6 xl:grid-cols-2">
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: motionTokens.card }} className="premium-panel min-w-0 p-5 sm:p-6" aria-labelledby="class-performance-title"><div id="class-performance-title"><ChartHeader title="Completed-attempt performance" subtitle="Completed attempts by score band" /></div><div className="mt-5 h-64" role="img" aria-label="Completed attempts by score band"><ResponsiveContainer width="100%" height="100%"><BarChart data={scores} margin={{ left: -20, right: 8, bottom: 8 }}><CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} /><XAxis dataKey="band" tick={{ fill: "#a1a1aa", fontSize: 10 }} axisLine={false} tickLine={false} interval={0} /><YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: "rgba(255,255,255,.025)" }} contentStyle={{ background: "#121216", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, boxShadow: "0 16px 40px rgba(0,0,0,.35)", fontSize: 12 }} formatter={(value) => [value, "Attempts"]} /><Bar dataKey="attempts" fill="#ff3045" radius={[5, 5, 1, 1]} animationDuration={reduced ? 0 : 420} isAnimationActive={!reduced} /></BarChart></ResponsiveContainer></div></motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .06, duration: motionTokens.card }} className="premium-panel p-5 sm:p-6"><ChartHeader title="Topics needing attention" subtitle="Weakest confirmed-answer accuracy first" /><RankedBars items={topics} label="Topics ranked by ascending accuracy" /></motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .12, duration: motionTokens.card }} className="premium-panel p-5 sm:p-6"><ChartHeader title="Misconception signals" subtitle="Selected incorrect-answer patterns only" /><RankedBars items={misconceptionSignals} label="Misconceptions ranked by occurrence" />{misconceptionSignals.length > 0 && <details className="signal-details"><summary>Full signal descriptions</summary><ol>{misconceptionSignals.map((item, index) => <li key={`${item.fullLabel}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><MixedText text={item.fullLabel} language={textLanguage(item.fullLabel)} /></li>)}</ol></details>}</motion.section>
        <motion.section initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : .18, duration: motionTokens.card }} className="premium-panel min-w-0 p-5 sm:p-6"><ChartHeader title="Difficulty distribution" subtitle="Confirmed questions at each actual difficulty level" /><div className="mt-5 h-64" role="img" aria-label="Confirmed question difficulty distribution from level one to five"><ResponsiveContainer width="100%" height="100%"><BarChart data={difficulty} margin={{ left: -20, right: 8, bottom: 8 }}><CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} /><XAxis dataKey="difficulty" tick={{ fill: "#a1a1aa", fontSize: 10 }} axisLine={false} tickLine={false} interval={0} /><YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: "rgba(255,255,255,.025)" }} contentStyle={{ background: "#121216", border: "1px solid rgba(255,255,255,.1)", borderRadius: 12, boxShadow: "0 16px 40px rgba(0,0,0,.35)", fontSize: 12 }} formatter={(value) => [value, "Questions"]} /><Bar dataKey="count" fill="#ff3045" radius={[5, 5, 1, 1]} animationDuration={reduced ? 0 : 420} isAnimationActive={!reduced} /></BarChart></ResponsiveContainer></div><div className="difficulty-scale" aria-hidden>{[1, 2, 3, 4, 5].map((level) => <span key={level}>Level {level}</span>)}</div></motion.section>
      </div>
      <section className="premium-panel overflow-hidden"><div className="table-heading"><div><h2 className="text-base font-semibold text-white">Student attempts</h2><p className="mt-1.5 text-xs text-zinc-500">One row per durable assessment attempt</p></div><span className="table-scroll-hint">Scroll to review all metrics →</span></div><div className="student-table-wrap" role="region" aria-label="Live student attempts table" tabIndex={0}><table className="student-table"><thead><tr><th>Student</th><th>Language</th><th>Status</th><th>Answered</th><th>Accuracy</th><th>Correct</th><th>Incorrect</th><th>Difficulty</th></tr></thead><tbody>{data.students.map((attempt) => <tr key={attempt.attempt_id}><td className="student-name"><MixedText text={attempt.student_id} language={attempt.language} /><small className="attempt-reference">Attempt · {attempt.attempt_id.slice(0, 8)}</small></td><td><span className="meta-chip">{attempt.language === "ar" ? "Arabic" : "English"}</span></td><td><span className={`table-status ${attempt.status === "completed" ? "complete" : "incomplete"}`}>{attempt.status === "completed" ? "Completed" : "In progress"}</span></td><td className="numeric-cell">{attempt.answered}</td><td className="numeric-cell">{attempt.accuracy}%</td><td className="numeric-cell">{attempt.correct}</td><td className="numeric-cell">{attempt.incorrect}</td><td className="numeric-cell">{attempt.final_difficulty ?? attempt.initial_difficulty} / 5</td></tr>)}</tbody></table></div></section>
      <p className="flex items-center gap-2 text-[11px] text-zinc-600"><BarChart3 size={13} aria-hidden /> Only confirmed durable answers contribute to performance analytics.</p>
    </div>
  );
}

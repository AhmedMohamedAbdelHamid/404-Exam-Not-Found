"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { BarChart3, GraduationCap, Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { motionTokens } from "@/lib/motion";

const navigation = [
  { href: "/", label: "Assessment", icon: GraduationCap },
  { href: "/teacher", label: "Teacher Dashboard", icon: BarChart3 },
];

function Logo() {
  return (
    <Link href="/" className="group flex items-center gap-3" aria-label="Exam Not Found home">
      <span className="grid size-11 place-items-center rounded-xl border border-red-500/20 bg-red-500/8 text-lg font-black tracking-[-0.08em] text-white shadow-[0_10px_35px_rgba(255,48,69,.08)]">
        404<span className="text-[#ff3045]">.</span>
      </span>
      <span className="leading-tight">
        <strong className="block text-sm font-semibold tracking-[-0.02em] text-white">Exam Not Found</strong>
        <small className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">Adaptive learning</small>
      </span>
    </Link>
  );
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  return (
    <nav aria-label="Primary navigation" className="mt-12 space-y-2">
      <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-600">Workspace</p>
      {navigation.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" || pathname.startsWith("/assessment") || pathname.startsWith("/results") : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={`relative flex items-center gap-3 rounded-xl px-3 py-3 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#ff6576] ${active ? "text-white" : "text-zinc-400 hover:bg-white/[.035] hover:text-zinc-100"}`}
          >
            {active && (
              <motion.span
                layoutId="active-navigation"
                transition={reduced ? { duration: 0 } : motionTokens.spring}
                className="absolute inset-0 -z-10 rounded-xl border border-red-500/15 bg-red-500/[.09]"
              />
            )}
            <Icon size={17} strokeWidth={1.7} aria-hidden />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-20 overflow-hidden bg-[#050506]">
      <div className="ambient-orb absolute -right-40 -top-56 size-[720px] rounded-full bg-red-700/[.10] blur-[130px]" />
      <div className="absolute -bottom-80 left-[18%] size-[620px] rounded-full bg-red-950/[.12] blur-[150px]" />
      <div className="ambient-grid absolute inset-0 opacity-[.22]" />
      <div className="noise absolute inset-0 opacity-[.025]" />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const reduced = useReducedMotion();
  return (
    <div className="min-h-screen text-zinc-100">
      <AmbientBackground />
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[260px] border-r border-white/[.06] bg-[#080809]/85 px-5 py-7 backdrop-blur-xl lg:block">
        <Logo />
        <Navigation />
        <div className="absolute inset-x-5 bottom-7 rounded-xl border border-white/[.06] bg-white/[.025] p-4">
          <div className="flex items-center gap-2 text-[11px] font-medium text-zinc-300">
            <ShieldCheck size={14} className="text-[#ff6576]" aria-hidden /> Secure assessment
          </div>
          <p className="mt-2 text-[11px] leading-5 text-zinc-500">Answer keys remain server-side. Progress is reconciled safely.</p>
        </div>
      </aside>

      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-white/[.06] bg-[#070708]/90 px-4 backdrop-blur-xl lg:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} className="icon-button" aria-label="Open navigation">
          <Menu size={20} />
        </button>
      </header>
      <AnimatePresence>
        {open && (
          <>
            <motion.button
              aria-label="Close navigation"
              className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-[290px] border-r border-white/10 bg-[#09090b] p-6 lg:hidden"
              initial={reduced ? { opacity: 0 } : { x: -320 }} animate={reduced ? { opacity: 1 } : { x: 0 }} exit={reduced ? { opacity: 0 } : { x: -320 }}
              transition={{ type: "spring", stiffness: 360, damping: 36 }}
            >
              <div className="flex items-center justify-between"><Logo /><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={19} /></button></div>
              <Navigation onNavigate={() => setOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
      <main className="min-h-screen lg:pl-[260px]">
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduced ? 0 : motionTokens.page, ease: motionTokens.ease }}
          className="mx-auto w-full max-w-[1460px] px-4 py-8 sm:px-7 lg:px-10 lg:py-10 xl:px-14"
        >{children}</motion.div>
      </main>
    </div>
  );
}

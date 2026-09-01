"use client";

import { Timer, Zap } from "lucide-react";
import type { ResolutionTimeline } from "@/lib/types";

/** Instantaneous (<30s) AI dispute risk-resolution trace with timestamped reasoning. */
export default function RiskResolutionLog({ timeline }: { timeline: ResolutionTimeline }) {
  return (
    <div className="rounded-xl border border-emerald-400/25 bg-base-900/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
          <Zap className="h-3 w-3" /> AI Risk Resolution Log
        </p>
        <span className="flex items-center gap-1 rounded-full bg-emerald-400/10 px-2 py-0.5 text-[9px] font-bold text-emerald-400">
          <Timer className="h-2.5 w-2.5" /> Resolved in {(timeline.resolved_ms / 1000).toFixed(2)}s · SLA {timeline.sla_seconds}s
        </span>
      </div>
      <ol className="mt-3 space-y-2">
        {timeline.steps.map((step, index) => (
          <li key={index} className="flex items-start gap-2.5">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-emerald-400/10 text-[9px] font-bold text-emerald-400">{index + 1}</span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-baseline justify-between gap-x-2">
                <span className="text-[11px] font-semibold text-ink-100">{step.phase}</span>
                <span className="font-mono text-[9px] text-ink-700">+{step.ms}ms · {new Date(step.at).toLocaleTimeString()}</span>
              </span>
              <span className="mt-0.5 block text-[10px] leading-relaxed text-ink-500">{step.detail}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

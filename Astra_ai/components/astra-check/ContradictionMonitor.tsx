"use client";

import { Activity, CheckCircle2, AlertTriangle } from "lucide-react";

const LOG = [
  { time: "14:02:11.203", check: "Goal conflict scan", result: "clear" },
  { time: "14:02:11.188", check: "Duplicate purchase scan", result: "clear" },
  { time: "14:02:11.151", check: "Spend-cap contradiction", result: "clear" },
  { time: "14:02:10.994", check: "Category risk cross-check", result: "flagged" },
  { time: "14:02:10.960", check: "Seller blacklist match", result: "clear" },
] as const;

export default function ContradictionMonitor() {
  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-astra-cyan" />
          <h2 className="font-display text-sm font-semibold text-ink-100">
            Contradiction Checker
          </h2>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
          <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-signal-good" />
          Live monitor
        </span>
      </div>

      <div className="scroll-thin max-h-64 space-y-2 overflow-y-auto pr-1">
        {LOG.map((l, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded-lg border border-base-600 bg-base-800/50 px-3 py-2"
          >
            <div className="flex items-center gap-2">
              {l.result === "clear" ? (
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-signal-good" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-signal-hold" />
              )}
              <span className="text-[11px] text-ink-300">{l.check}</span>
            </div>
            <span className="shrink-0 font-mono text-[10px] text-ink-700">{l.time}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

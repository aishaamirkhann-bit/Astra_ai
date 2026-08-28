"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Zap,
  Calculator,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  RotateCcw,
  X,
} from "lucide-react";
import type { PipelineStateOut } from "@/lib/types";

const ICONS: Record<string, typeof Zap> = {
  intent: Zap,
  finance: Calculator,
  contradiction: ShieldAlert,
  trust: ShieldCheck,
  approval: UserCheck,
  checkout: RotateCcw,
};

// This node-trail is ASTRA's signature: every purchase visibly passes through
// a deterministic rules chain before a human ever sees an approval prompt.
export default function PipelineBar({ pipeline }: { pipeline: PipelineStateOut }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const { nodes, active_index: activeIndex } = pipeline;

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-ink-100">
          ASTRA Decision Pipeline
        </h2>
        {pipeline.is_live && (
          <span className="flex items-center gap-1.5 rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
            <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-signal-good" /> Live
          </span>
        )}
      </div>

      <div className="relative">
        {/* connecting rail */}
        <div className="absolute left-0 right-0 top-5 h-px bg-base-600" />
        <div
          className="absolute left-0 top-5 h-px bg-astra-gradient transition-all duration-700"
          style={{ width: `${(activeIndex / (nodes.length - 1)) * 100}%` }}
        />

        <div className="relative grid grid-cols-3 gap-y-6 sm:grid-cols-6">
          {nodes.map(({ key, label, status, latency_display }, i) => {
            const Icon = ICONS[key] ?? Zap;
            const done = status === "done";
            const active = status === "active";
            return (
              <button
                key={key}
                onClick={() => setOpenIndex(i)}
                className="group flex flex-col items-center gap-2 text-center"
              >
                <span
                  className={[
                    "grid h-10 w-10 place-items-center rounded-full border transition-all",
                    done && "border-astra-indigo bg-astra-gradient-soft",
                    active && "border-astra-violet bg-astra-gradient shadow-glow animate-pulseDot",
                    !done && !active && "border-base-600 bg-base-800",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <Icon
                    className={[
                      "h-4 w-4",
                      active ? "text-white" : done ? "text-astra-cyan" : "text-ink-500",
                    ].join(" ")}
                  />
                </span>
                <span className="max-w-[80px] text-[10px] font-medium leading-tight text-ink-300 group-hover:text-ink-100">
                  {label}
                </span>
                <span className="font-mono text-[10px] text-ink-700">{latency_display}</span>
              </button>
            );
          })}
        </div>
      </div>

      {openIndex !== null && (
        <div className="mt-5 flex items-start gap-3 rounded-lg border border-base-600 bg-base-900/70 p-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-ink-100">{nodes[openIndex].label}</p>
            <p className="mt-1 font-mono text-[11px] text-ink-500">{nodes[openIndex].log}</p>
          </div>
          <button
            onClick={() => setOpenIndex(null)}
            aria-label="Close node detail"
            className="text-ink-500 hover:text-ink-100"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <Link
        href="/astra-check"
        className="mt-5 flex items-center justify-between rounded-lg bg-signal-hold/5 px-4 py-3 transition-colors hover:bg-signal-hold/10"
      >
        <span className="text-[11px] text-ink-500">Current Verdict</span>
        <span className="font-display text-sm font-semibold text-signal-hold">
          {pipeline.current_verdict_label}
        </span>
      </Link>
    </section>
  );
}

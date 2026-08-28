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

const NODES = [
  { label: "Intent Received", icon: Zap, latency: "8ms", log: "Parsed voice/text intent → structured query." },
  { label: "Finance Rules", icon: Calculator, latency: "42ms", log: "Checked against budget cap and wallet balance." },
  { label: "Contradiction Check", icon: ShieldAlert, latency: "31ms", log: "No conflicting prior commitments found." },
  { label: "Trust Engine", icon: ShieldCheck, latency: "68ms", log: "Seller trust score computed: 4.8 / 5." },
  { label: "Human Approval", icon: UserCheck, latency: "waiting", log: "Awaiting your confirmation." },
  { label: "Reversible Checkout", icon: RotateCcw, latency: "queued", log: "30s reversal window will open on approval." },
] as const;

// This node-trail is ASTRA's signature: every purchase visibly passes through
// a deterministic rules chain before a human ever sees an approval prompt.
export default function PipelineBar() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const activeIndex = 4; // "Human Approval" is currently pending in this demo state

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-ink-100">
          ASTRA Decision Pipeline
        </h2>
        <span className="flex items-center gap-1.5 rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
          <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-signal-good" /> Live
        </span>
      </div>

      <div className="relative">
        {/* connecting rail */}
        <div className="absolute left-0 right-0 top-5 h-px bg-base-600" />
        <div
          className="absolute left-0 top-5 h-px bg-astra-gradient transition-all duration-700"
          style={{ width: `${(activeIndex / (NODES.length - 1)) * 100}%` }}
        />

        <div className="relative grid grid-cols-3 gap-y-6 sm:grid-cols-6">
          {NODES.map(({ label, icon: Icon, latency }, i) => {
            const done = i < activeIndex;
            const active = i === activeIndex;
            return (
              <button
                key={label}
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
                <span className="font-mono text-[10px] text-ink-700">{latency}</span>
              </button>
            );
          })}
        </div>
      </div>

      {openIndex !== null && (
        <div className="mt-5 flex items-start gap-3 rounded-lg border border-base-600 bg-base-900/70 p-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-ink-100">{NODES[openIndex].label}</p>
            <p className="mt-1 font-mono text-[11px] text-ink-500">{NODES[openIndex].log}</p>
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
          Waiting on Approval
        </span>
      </Link>
    </section>
  );
}

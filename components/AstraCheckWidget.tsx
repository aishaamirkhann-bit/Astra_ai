"use client";

import Link from "next/link";
import { Wallet2, ShieldCheck, Tags, ArrowUpRight, CheckCircle2 } from "lucide-react";

const CHECKS = [
  { label: "Financial Fit", detail: "Within your budget", icon: Wallet2, verdict: "Good" },
  { label: "Seller Trust", detail: "Highly rated by buyers", icon: ShieldCheck, verdict: "Good" },
  { label: "Price Fairness", detail: "Better than market avg.", icon: Tags, verdict: "Good" },
] as const;

export default function AstraCheckWidget() {
  return (
    <section className="glass glass-hover rounded-xl2 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-ink-100">ASTRA Check</h2>
        <span className="rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
          Live
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {CHECKS.map(({ label, detail, icon: Icon, verdict }) => (
          <div key={label} className="flex items-center gap-3">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-base-800">
              <Icon className="h-4 w-4 text-astra-cyan" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-ink-100">{label}</p>
              <p className="truncate text-[11px] text-ink-500">{detail}</p>
            </div>
            <span className="shrink-0 rounded-full bg-signal-good/10 px-2 py-1 text-[10px] font-semibold text-signal-good">
              {verdict}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-5 rounded-xl border border-signal-good/25 bg-signal-good/5 p-4 text-center">
        <div className="flex items-center justify-center gap-1.5">
          <CheckCircle2 className="h-4 w-4 text-signal-good" />
          <p className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
            Overall Verdict
          </p>
        </div>
        <p className="mt-1 font-display text-lg font-bold text-signal-good">GOOD TO BUY</p>
        <Link
          href="/astra-check"
          className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-ink-300 hover:text-ink-100"
        >
          See Full Analysis <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </section>
  );
}

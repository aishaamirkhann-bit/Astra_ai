import Link from "next/link";
import { Wallet2, ShieldCheck, Tags, ArrowUpRight, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import type { AstraCheckOut, Verdict } from "@/lib/types";

const ICONS = [Wallet2, ShieldCheck, Tags] as const;

const VERDICT_STYLES: Record<Verdict, { badge: string; icon: typeof CheckCircle2 }> = {
  Good: { badge: "bg-signal-good/10 text-signal-good", icon: CheckCircle2 },
  Warning: { badge: "bg-signal-hold/10 text-signal-hold", icon: AlertTriangle },
  Bad: { badge: "bg-signal-reject/10 text-signal-reject", icon: XCircle },
};

const OVERALL_STYLES: Record<AstraCheckOut["overall_verdict"], string> = {
  "GOOD TO BUY": "text-signal-good",
  "REVIEW SUGGESTED": "text-signal-hold",
  "NOT RECOMMENDED": "text-signal-reject",
};

export default function AstraCheckWidget({ astraCheck }: { astraCheck: AstraCheckOut }) {
  const OverallIcon = VERDICT_STYLES[
    astraCheck.checks.find((c) => c.verdict !== "Good")?.verdict ?? "Good"
  ].icon;
  return (
    <section className="glass glass-hover rounded-xl2 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-ink-100">ASTRA Check</h2>
        <span className="rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
          Live
        </span>
      </div>

      <div className="flex flex-col gap-3">
        {astraCheck.checks.map(({ label, detail, verdict }, i) => {
          const Icon = ICONS[i] ?? Wallet2;
          return (
            <div key={label} className="flex items-center gap-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-base-800">
                <Icon className="h-4 w-4 text-astra-cyan" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-ink-100">{label}</p>
                <p className="truncate text-[11px] text-ink-500">{detail}</p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${VERDICT_STYLES[verdict].badge}`}
              >
                {verdict}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-5 rounded-xl border border-signal-good/25 bg-signal-good/5 p-4 text-center">
        <div className="flex items-center justify-center gap-1.5">
          <OverallIcon className="h-4 w-4 text-signal-good" />
          <p className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
            Overall Verdict
          </p>
        </div>
        <p className={`mt-1 font-display text-lg font-bold ${OVERALL_STYLES[astraCheck.overall_verdict]}`}>
          {astraCheck.overall_verdict}
        </p>
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

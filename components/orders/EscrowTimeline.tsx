"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, ChevronDown, Landmark } from "lucide-react";
import { getOrderTimeline } from "@/lib/api";
import type { OrderTimeline } from "@/lib/api";
import RiskResolutionLog from "@/components/orders/RiskResolutionLog";

const STATUS_STYLES: Record<string, string> = {
  done: "border-violet-400 bg-astra-gradient text-white",
  active: "border-signal-hold/60 bg-signal-hold/15 text-signal-hold",
  pending: "border-base-600 bg-base-900 text-ink-700",
  cancelled: "border-signal-reject/50 bg-signal-reject/15 text-signal-reject",
};

/** Escrow lifecycle + collapsible ASTRA AI reasoning log for one order. */
export default function EscrowTimeline({ orderRef, showResolutionLog = true }: { orderRef: string; showResolutionLog?: boolean }) {
  const [timeline, setTimeline] = useState<OrderTimeline | null>(null);
  const [logOpen, setLogOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getOrderTimeline(orderRef)
      .then((result) => { if (!cancelled) setTimeline(result); })
      .catch(() => { if (!cancelled) setTimeline(null); });
    return () => { cancelled = true; };
  }, [orderRef]);

  if (!timeline) return null;

  return (
    <div className="mt-5 rounded-xl border border-base-600 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-xs font-semibold text-ink-100">
          <Landmark className="h-3.5 w-3.5 text-astra-cyan" /> Escrow timeline
        </p>
        <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${timeline.escrow_status === "REFUNDED" ? "bg-signal-reject/10 text-signal-reject" : timeline.escrow_status === "RELEASED" ? "bg-signal-good/10 text-signal-good" : "bg-signal-hold/10 text-signal-hold"}`}>
          {timeline.escrow_status}
        </span>
      </div>

      <ol className="mt-3 flex flex-col gap-2">
        {timeline.stages.map((stage) => (
          <li key={stage.key} className="flex items-center gap-2.5">
            <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[9px] font-bold ${STATUS_STYLES[stage.status] ?? STATUS_STYLES.pending}`}>
              {stage.status === "done" ? "✓" : stage.status === "cancelled" ? "✕" : "•"}
            </span>
            <span className="flex-1 text-[11px] text-ink-300">{stage.label}</span>
            {stage.at && <span className="font-mono text-[9px] text-ink-700">{new Date(stage.at).toLocaleTimeString()}</span>}
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={() => setLogOpen((v) => !v)}
        aria-expanded={logOpen}
        className="mt-3 flex w-full items-center justify-between rounded-lg bg-base-900 px-3 py-2 text-[10px] font-semibold text-ink-300 hover:text-ink-100"
      >
        <span className="flex items-center gap-1.5"><BrainCircuit className="h-3 w-3 text-astra-cyan" /> ASTRA AI Reasoning Log</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${logOpen ? "rotate-180" : ""}`} />
      </button>
      {logOpen && (
        <ul className="mt-2 flex flex-col gap-2 rounded-lg bg-base-900 p-3">
          {timeline.reasoning.map((entry, index) => (
            <li key={index} className="text-[10px] leading-relaxed text-ink-500">
              <span className="font-mono text-ink-700">{entry.at ? new Date(entry.at).toLocaleString() : "—"}</span>{" "}
              <span className="font-semibold text-ink-300">{entry.step}:</span> {entry.detail}
            </li>
          ))}
        </ul>
      )}
      {showResolutionLog && timeline.resolution_timeline && <div className="mt-3"><RiskResolutionLog timeline={timeline.resolution_timeline} /></div>}
    </div>
  );
}

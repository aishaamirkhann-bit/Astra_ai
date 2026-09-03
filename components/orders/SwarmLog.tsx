"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Network, Timer } from "lucide-react";
import { getOrderSwarmLog } from "@/lib/api";
import type { SwarmTrace } from "@/lib/types";

const AGENT_STYLES: Record<string, string> = {
  "pricing-agent": "text-cyan-300 bg-cyan-400/10",
  "risk-agent": "text-rose-300 bg-rose-400/10",
  "logistics-agent": "text-amber-300 bg-amber-400/10",
};

/** Collapsible ASTRA Swarm Log — parallel Pricing/Risk/Logistics sub-agents during order verification. */
export default function SwarmLog({ orderRef }: { orderRef: string }) {
  const [trace, setTrace] = useState<SwarmTrace | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let live = true;
    getOrderSwarmLog(orderRef).then((result) => { if (live) setTrace(result); }).catch(() => undefined);
    return () => { live = false; };
  }, [orderRef]);

  if (!trace) return null;

  return (
    <div className="mt-5 rounded-xl border border-base-600 p-4 print:hidden">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="flex w-full items-center justify-between gap-2 text-left">
        <span className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-ink-300">
          <Network className="h-3 w-3 text-astra-cyan" /> ASTRA Swarm Log
        </span>
        <span className="flex items-center gap-2">
          <span className="flex items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold text-violet-400">
            <Timer className="h-2.5 w-2.5" /> {trace.agents.length} agents · {trace.total_ms}ms
          </span>
          <ChevronDown className={`h-3 w-3 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`} />
        </span>
      </button>
      {open && <div className="mt-3 space-y-3">
        <p className="text-[9px] text-ink-700">Orchestrator: {trace.orchestrator} · parallelism ×{trace.parallelism} · started {new Date(trace.started_at).toLocaleTimeString()}</p>
        {trace.agents.map((agent) => (
          <div key={agent.agent} className="rounded-lg border border-base-600 bg-base-900/60 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className={`rounded-full px-2 py-0.5 font-mono text-[9px] font-bold ${AGENT_STYLES[agent.agent] ?? "bg-base-800 text-ink-300"}`}>{agent.agent}</span>
              <span className="text-[9px] capitalize text-ink-500">{agent.role} · {agent.status}</span>
            </div>
            <ul className="mt-2 space-y-1">
              {agent.tasks.map((task) => (
                <li key={task.task} className="flex items-baseline justify-between gap-2 font-mono text-[9px]">
                  <span className="min-w-0 flex-1 truncate text-ink-300">{task.task} <span className="text-ink-700">— {task.detail}</span></span>
                  <span className="shrink-0 text-ink-700">{task.start_ms}–{task.end_ms}ms · {task.status}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="flex items-center justify-between rounded-lg bg-astra-gradient-soft px-3 py-2 font-mono text-[9px] text-ink-100">
          <span>{trace.merge.task} — {trace.merge.detail}</span>
          <span>{trace.merge.start_ms}–{trace.merge.end_ms}ms · {trace.merge.status}</span>
        </div>
      </div>}
    </div>
  );
}

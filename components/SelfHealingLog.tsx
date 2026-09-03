"use client";

import { useEffect, useState } from "react";
import { ChevronUp, HeartPulse, ShieldCheck } from "lucide-react";
import { pingBackendHealth } from "@/lib/api";
import { pushAgentLog, subscribeAgentLog, type AgentLogEntry } from "@/lib/agentLog";

const SEVERITY_STYLES: Record<AgentLogEntry["severity"], string> = {
  info: "text-astra-cyan",
  warn: "text-amber-400",
  recovered: "text-emerald-400",
};

/** Feature 8 — visual log of the self-healing fallback engine rerouting failed API transactions. */
export default function SelfHealingLog() {
  const [entries, setEntries] = useState<AgentLogEntry[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => subscribeAgentLog(setEntries), []);

  useEffect(() => {
    let live = true;
    void pingBackendHealth().then((probe) => {
      if (!live) return;
      pushAgentLog({
        agent: "Fallback-Engine",
        severity: probe.ok ? "info" : "warn",
        route: "GET /health",
        detail: probe.ok
          ? `Self-healing engine armed — backend reachable in ${probe.latencyMs}ms. Monitoring all API transactions.`
          : `Backend probe failed after ${probe.latencyMs}ms — fallback gateway on standby.`,
        latencyMs: probe.latencyMs,
      });
    });
    return () => { live = false; };
  }, []);

  if (entries.length === 0) return null;
  const recovered = entries.filter((entry) => entry.severity === "recovered").length;

  return (
    <div className="fixed bottom-5 left-5 z-40 max-w-xs print:hidden">
      {open && (
        <div className="mb-2 max-h-64 w-72 overflow-y-auto rounded-xl border border-base-600 bg-base-950/95 p-3 shadow-2xl backdrop-blur">
          <p className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-ink-300">
            <HeartPulse className="h-3 w-3 text-astra-cyan" /> Self-Healing Fallback Engine
          </p>
          <ul className="mt-2 space-y-1.5">
            {[...entries].reverse().map((entry) => (
              <li key={entry.id} className="rounded-lg bg-base-900/70 p-2">
                <p className="flex items-center justify-between gap-2 font-mono text-[8px] text-ink-700">
                  <span className={`font-bold ${SEVERITY_STYLES[entry.severity]}`}>{entry.agent} · {entry.severity.toUpperCase()}</span>
                  <span>{new Date(entry.at).toLocaleTimeString()}</span>
                </p>
                <p className="mt-0.5 font-mono text-[9px] text-ink-300">{entry.route}</p>
                <p className="mt-0.5 text-[9px] leading-relaxed text-ink-500">{entry.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-base-600 bg-base-950/95 px-3 py-2 text-[10px] font-semibold text-ink-300 shadow-card backdrop-blur hover:text-ink-100"
      >
        <ShieldCheck className={`h-3.5 w-3.5 ${recovered > 0 ? "text-emerald-400" : "text-astra-cyan"}`} />
        <span className="hidden sm:inline">Self-Healing Engine · {entries.length} event{entries.length === 1 ? "" : "s"}</span>
        <span className="sm:hidden">{entries.length}</span>
        <ChevronUp className={`h-3 w-3 text-ink-500 transition-transform ${open ? "" : "rotate-180"}`} />
      </button>
    </div>
  );
}

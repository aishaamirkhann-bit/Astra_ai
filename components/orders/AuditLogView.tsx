"use client";

import { useEffect, useState } from "react";
import { FileClock, RefreshCw } from "lucide-react";
import { getOrdersAudit } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";

const VERDICT_STYLES: Record<string, string> = {
  approve: "bg-signal-good/10 text-signal-good",
  approved: "bg-signal-good/10 text-signal-good",
  hold: "bg-signal-hold/10 text-signal-hold",
  reject: "bg-signal-reject/10 text-signal-reject",
  cancelled: "bg-signal-reject/10 text-signal-reject",
};

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function AuditLogView() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getOrdersAudit()
      .then((items) => setEntries(items))
      .catch((requestError: Error) => setError(requestError.message || "Could not load the audit trail."))
      .finally(() => setLoading(false));
  }, [reloadKey]);

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <FileClock className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">Audit Log</h2>
        <span className="ml-auto text-[10px] text-ink-700">Immutable · append-only</span>
        <button
          type="button"
          aria-label="Refresh audit log"
          onClick={() => setReloadKey((value) => value + 1)}
          className="rounded-lg border border-base-600 p-1.5 text-ink-500 transition hover:text-ink-100"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading ? (
        <p className="py-6 text-center text-xs text-ink-700">Loading audit trail…</p>
      ) : error ? (
        <p className="py-6 text-center text-xs text-signal-reject">{error}</p>
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-xs text-ink-700">
          No audit events yet — approvals, cancellations, reversals, and B2B consent evaluations will appear here.
        </p>
      ) : (
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-[11px]">
            <thead>
              <tr className="border-b border-base-600 text-ink-500">
                <th className="pb-2 font-medium">Event</th>
                <th className="pb-2 font-medium">Endpoint</th>
                <th className="pb-2 font-medium">Actor</th>
                <th className="pb-2 font-medium">Verdict</th>
                <th className="pb-2 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-base-700/60">
                  <td className="py-2.5 font-mono text-ink-300">{entry.type}</td>
                  <td className="py-2.5 font-mono text-ink-500">{entry.endpoint}</td>
                  <td className="py-2.5 text-ink-300">{entry.actor}</td>
                  <td className="py-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 font-semibold ${VERDICT_STYLES[entry.verdict] ?? "bg-base-800 text-ink-300"}`}
                    >
                      {entry.verdict}
                    </span>
                  </td>
                  <td className="py-2.5 font-mono text-ink-700">{formatTime(entry.time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

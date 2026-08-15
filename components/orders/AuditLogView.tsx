import { FileClock } from "lucide-react";
import { AUDIT_LOG } from "@/lib/mockData";

const VERDICT_STYLES = {
  approve: "bg-signal-good/10 text-signal-good",
  approved: "bg-signal-good/10 text-signal-good",
  hold: "bg-signal-hold/10 text-signal-hold",
  reject: "bg-signal-reject/10 text-signal-reject",
} as const;

export default function AuditLogView() {
  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <FileClock className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">Audit Log</h2>
        <span className="ml-auto text-[10px] text-ink-700">Immutable · append-only</span>
      </div>

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
            {AUDIT_LOG.map((e) => (
              <tr key={e.id} className="border-b border-base-700/60">
                <td className="py-2.5 font-mono text-ink-300">{e.type}</td>
                <td className="py-2.5 font-mono text-ink-500">{e.endpoint}</td>
                <td className="py-2.5 text-ink-300">{e.actor}</td>
                <td className="py-2.5">
                  <span
                    className={`rounded-full px-2 py-0.5 font-semibold ${VERDICT_STYLES[e.verdict as keyof typeof VERDICT_STYLES]}`}
                  >
                    {e.verdict}
                  </span>
                </td>
                <td className="py-2.5 font-mono text-ink-700">{e.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

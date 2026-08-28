"use client";

import { useState } from "react";
import { Terminal, Play, CheckCircle2, PauseCircle, XCircle } from "lucide-react";

const PROTOCOLS = ["UCP", "ACP"] as const;

const SAMPLE_PAYLOADS: Record<(typeof PROTOCOLS)[number], string> = {
  UCP: JSON.stringify(
    {
      protocol: "UCP/1.2",
      intent: "purchase",
      agent_id: "shopping-copilot-04",
      item: { sku: "SGS25U-256-BLK", price: 314999, currency: "PKR" },
      buyer_context: { wallet_balance: 135000, active_goals: ["laptop_fund"] },
    },
    null,
    2
  ),
  ACP: JSON.stringify(
    {
      protocol: "ACP/2.0",
      action: "checkout.request",
      agent: { id: "astra-orchestrator", trust_tier: "verified" },
      order: { total: 314999, currency: "PKR", reversible_window_s: 30 },
    },
    null,
    2
  ),
};

type Verdict = "approve" | "hold" | "reject" | null;

const VERDICT_META: Record<
  Exclude<Verdict, null>,
  { label: string; icon: typeof CheckCircle2; className: string; reason: string }
> = {
  approve: {
    label: "approve",
    icon: CheckCircle2,
    className: "text-signal-good bg-signal-good/10 border-signal-good/30",
    reason: "All deterministic rules passed; no contradictions found; seller trust above threshold.",
  },
  hold: {
    label: "hold",
    icon: PauseCircle,
    className: "text-signal-hold bg-signal-hold/10 border-signal-hold/30",
    reason: "Price exceeds weekly spend cap — routed to human approval before execution.",
  },
  reject: {
    label: "reject",
    icon: XCircle,
    className: "text-signal-reject bg-signal-reject/10 border-signal-reject/30",
    reason: "Seller trust score below minimum threshold for unattended agent checkout.",
  },
};

export default function PayloadSimulator() {
  const [protocol, setProtocol] = useState<(typeof PROTOCOLS)[number]>("UCP");
  const [payload, setPayload] = useState(SAMPLE_PAYLOADS.UCP);
  const [verdict, setVerdict] = useState<Verdict>(null);
  const [running, setRunning] = useState(false);

  const switchProtocol = (p: (typeof PROTOCOLS)[number]) => {
    setProtocol(p);
    setPayload(SAMPLE_PAYLOADS[p]);
    setVerdict(null);
  };

  const runSimulation = () => {
    setRunning(true);
    setVerdict(null);
    setTimeout(() => {
      const outcomes: Exclude<Verdict, null>[] = ["approve", "hold", "reject"];
      setVerdict(outcomes[Math.floor(Math.random() * outcomes.length)]);
      setRunning(false);
    }, 900);
  };

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-astra-cyan" />
          <h2 className="font-display text-sm font-semibold text-ink-100">
            Consent Adapter Playground
          </h2>
        </div>
        <span className="rounded-md bg-base-800 px-2 py-1 font-mono text-[10px] text-ink-500">
          POST /api/v1/consent/evaluate
        </span>
      </div>

      <div className="mb-3 inline-flex rounded-lg bg-base-800 p-1">
        {PROTOCOLS.map((p) => (
          <button
            key={p}
            onClick={() => switchProtocol(p)}
            className={[
              "rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors",
              protocol === p
                ? "bg-astra-gradient text-white shadow-glow"
                : "text-ink-500 hover:text-ink-100",
            ].join(" ")}
          >
            {p} payload
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            spellCheck={false}
            rows={12}
            className="scroll-thin w-full resize-none rounded-xl border border-base-600 bg-base-900 p-3 font-mono text-[11px] leading-relaxed text-ink-300 focus:outline-none"
          />
          <button
            onClick={runSimulation}
            disabled={running}
            className="mt-3 flex items-center gap-2 rounded-lg bg-astra-gradient px-4 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-60"
          >
            <Play className="h-3.5 w-3.5" />
            {running ? "Evaluating…" : "Run simulation"}
          </button>
        </div>

        <div className="rounded-xl border border-base-600 bg-base-800/40 p-4">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-wide text-ink-500">
            Live verdict
          </p>
          {!verdict && !running && (
            <p className="text-[11px] text-ink-700">Run a simulation to see the adapter's response.</p>
          )}
          {running && <p className="text-[11px] text-ink-500">Evaluating against rules engine…</p>}
          {verdict && (
            <div className={`rounded-xl border p-4 ${VERDICT_META[verdict].className}`}>
              <div className="flex items-center gap-2">
                {(() => {
                  const Icon = VERDICT_META[verdict].icon;
                  return <Icon className="h-5 w-5" />;
                })()}
                <p className="font-display text-sm font-bold uppercase tracking-wide">
                  {VERDICT_META[verdict].label}
                </p>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed opacity-90">
                {VERDICT_META[verdict].reason}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

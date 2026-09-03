"use client";

import { useState } from "react";
import { Terminal, Play, CheckCircle2, PauseCircle, XCircle, HelpCircle } from "lucide-react";
import { evaluateB2bPayload } from "@/lib/api";
import type { B2bEvaluation } from "@/lib/types";

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

type Verdict = "approve" | "hold" | "reject";

const VERDICT_META: Record<
  Verdict,
  { icon: typeof CheckCircle2; className: string }
> = {
  approve: {
    icon: CheckCircle2,
    className: "text-signal-good bg-signal-good/10 border-signal-good/30",
  },
  hold: {
    icon: PauseCircle,
    className: "text-signal-hold bg-signal-hold/10 border-signal-hold/30",
  },
  reject: {
    icon: XCircle,
    className: "text-signal-reject bg-signal-reject/10 border-signal-reject/30",
  },
};

export default function PayloadSimulator() {
  const [protocol, setProtocol] = useState<(typeof PROTOCOLS)[number]>("UCP");
  const [payload, setPayload] = useState(SAMPLE_PAYLOADS.UCP);
  const [evaluation, setEvaluation] = useState<B2bEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const switchProtocol = (p: (typeof PROTOCOLS)[number]) => {
    setProtocol(p);
    setPayload(SAMPLE_PAYLOADS[p]);
    setEvaluation(null);
    setError(null);
  };

  const runSimulation = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(payload) as Record<string, unknown>;
    } catch {
      setError("Payload is not valid JSON — fix the syntax and try again.");
      setEvaluation(null);
      return;
    }
    setRunning(true);
    setError(null);
    setEvaluation(null);
    try {
      setEvaluation(await evaluateB2bPayload(parsed));
    } catch (requestError) {
      setError((requestError as Error).message || "The consent adapter service is unavailable.");
    } finally {
      setRunning(false);
    }
  };

  const verdictMeta = evaluation ? VERDICT_META[evaluation.verdict] ?? null : null;
  const VerdictIcon = verdictMeta?.icon ?? HelpCircle;

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
          POST /api/v1/b2b/evaluate
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
            onClick={() => void runSimulation()}
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
          {!evaluation && !running && !error && (
            <p className="text-[11px] text-ink-700">Run a simulation to see the adapter's response.</p>
          )}
          {running && <p className="text-[11px] text-ink-500">Evaluating against rules engine…</p>}
          {error && <p className="text-[11px] text-signal-reject">{error}</p>}
          {evaluation && verdictMeta && (
            <div className={`rounded-xl border p-4 ${verdictMeta.className}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <VerdictIcon className="h-5 w-5" />
                  <p className="font-display text-sm font-bold uppercase tracking-wide">
                    {evaluation.verdict}
                  </p>
                </div>
                <span className="font-mono text-[10px] opacity-70">{evaluation.event_ref}</span>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed opacity-90">
                {evaluation.reason}
              </p>
              <ul className="mt-3 flex flex-col gap-1.5">
                {evaluation.checks.map((check) => (
                  <li key={check.rule} className="flex items-start gap-2 text-[10px] opacity-80">
                    <span
                      className={[
                        "mt-0.5 rounded px-1 font-mono font-semibold uppercase",
                        check.status === "pass" ? "bg-signal-good/15 text-signal-good" : check.status === "warn" ? "bg-signal-hold/15 text-signal-hold" : "bg-signal-reject/15 text-signal-reject",
                      ].join(" ")}
                    >
                      {check.status}
                    </span>
                    <span>
                      <span className="font-mono">{check.rule}</span> — {check.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

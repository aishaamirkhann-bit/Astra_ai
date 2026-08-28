"use client";

import { useMemo, useState } from "react";
import { Calculator, CheckCircle2, AlertTriangle } from "lucide-react";

const WALLET_BALANCE = 135000;
const MONTHLY_CAP = 60000;

export default function AffordabilityAnalyzer() {
  const [price, setPrice] = useState(180000);
  const [months, setMonths] = useState(6);

  const { emi, withinBalance, withinCap, verdict } = useMemo(() => {
    const emi = Math.round(price / months);
    const withinBalance = price <= WALLET_BALANCE * 1.5;
    const withinCap = emi <= MONTHLY_CAP;
    const verdict = withinBalance && withinCap ? "Affordable" : withinCap ? "Manageable" : "Stretch";
    return { emi, withinBalance, withinCap, verdict };
  }, [price, months]);

  // Static class lookup (not string-interpolated) so Tailwind's JIT scanner picks these up.
  const styles = {
    Affordable: {
      border: "border-signal-good/25",
      bg: "bg-signal-good/5",
      text: "text-signal-good",
    },
    Manageable: {
      border: "border-signal-hold/25",
      bg: "bg-signal-hold/5",
      text: "text-signal-hold",
    },
    Stretch: {
      border: "border-signal-reject/25",
      bg: "bg-signal-reject/5",
      text: "text-signal-reject",
    },
  } as const;
  const s = styles[verdict as keyof typeof styles];

  return (
    <section className="glass h-fit rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Calculator className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">Affordability Analyzer</h2>
      </div>

      <div className="mb-4">
        <div className="mb-1.5 flex items-center justify-between">
          <label className="text-[11px] text-ink-500">Candidate price</label>
          <span className="font-mono text-[11px] text-ink-100">Rs. {price.toLocaleString()}</span>
        </div>
        <input
          type="range"
          min={10000}
          max={500000}
          step={5000}
          value={price}
          onChange={(e) => setPrice(Number(e.target.value))}
          className="w-full accent-astra-violet"
        />
      </div>

      <div className="mb-5">
        <div className="mb-1.5 flex items-center justify-between">
          <label className="text-[11px] text-ink-500">Installment period</label>
          <span className="font-mono text-[11px] text-ink-100">{months} months</span>
        </div>
        <input
          type="range"
          min={1}
          max={12}
          step={1}
          value={months}
          onChange={(e) => setMonths(Number(e.target.value))}
          className="w-full accent-astra-violet"
        />
      </div>

      <div className="grid grid-cols-2 gap-3 text-[11px]">
        <div className="rounded-lg border border-base-600 bg-base-800/50 p-3">
          <p className="text-ink-500">Estimated EMI</p>
          <p className="mt-1 font-display text-sm font-semibold text-ink-100">
            Rs. {emi.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border border-base-600 bg-base-800/50 p-3">
          <p className="text-ink-500">Monthly cap</p>
          <p className="mt-1 font-display text-sm font-semibold text-ink-100">
            Rs. {MONTHLY_CAP.toLocaleString()}
          </p>
        </div>
      </div>

      <div className={`mt-4 flex items-center gap-2 rounded-xl border p-3 ${s.border} ${s.bg}`}>
        {withinCap ? (
          <CheckCircle2 className={`h-4 w-4 ${s.text}`} />
        ) : (
          <AlertTriangle className={`h-4 w-4 ${s.text}`} />
        )}
        <div>
          <p className={`text-xs font-semibold ${s.text}`}>{verdict}</p>
          <p className="text-[10px] text-ink-500">
            {withinBalance ? "Within wallet + goal buffer" : "Exceeds comfortable buffer"} ·{" "}
            {withinCap ? "EMI fits monthly cap" : "EMI exceeds monthly cap"}
          </p>
        </div>
      </div>
    </section>
  );
}

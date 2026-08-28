"use client";

import { useState } from "react";
import { ShieldCheck, Store } from "lucide-react";

const MARKETPLACES = [
  { name: "TechBazaar Official", price: "Rs. 314,999", verified: true },
  { name: "Daraz Mega Store", price: "Rs. 322,500", verified: true },
  { name: "MobileHub PK", price: "Rs. 308,999", verified: false },
];

export default function TrustInspectionPanel() {
  const [selected, setSelected] = useState(0);

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">
          Trust Verification &amp; Price Comparison
        </h2>
      </div>

      <div className="flex flex-col gap-2">
        {MARKETPLACES.map((m, i) => (
          <button
            key={m.name}
            onClick={() => setSelected(i)}
            className={[
              "flex items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors",
              selected === i
                ? "border-astra-violet/50 bg-astra-gradient-soft"
                : "border-base-600 bg-base-800/50 hover:border-base-500",
            ].join(" ")}
          >
            <div className="flex items-center gap-2.5">
              <div className="grid h-7 w-7 place-items-center rounded-lg bg-base-700">
                <Store className="h-3.5 w-3.5 text-ink-300" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-100">{m.name}</p>
                <p
                  className={[
                    "text-[10px]",
                    m.verified ? "text-signal-good" : "text-ink-700",
                  ].join(" ")}
                >
                  {m.verified ? "Verified seller" : "Unverified"}
                </p>
              </div>
            </div>
            <p className="font-display text-sm font-semibold text-ink-100">{m.price}</p>
          </button>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-base-600 bg-base-800/40 p-3 text-[11px] text-ink-500">
        Lowest verified price highlighted automatically. Unverified sellers are shown for
        comparison but excluded from the ASTRA Check trust score.
      </div>
    </section>
  );
}

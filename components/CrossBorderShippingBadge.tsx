"use client";

import { useEffect, useState } from "react";
import { Globe2 } from "lucide-react";
import { getCountry, getSavedCountry, isCountryCode, shippingEta, type CountryCode } from "@/lib/region";

export default function CrossBorderShippingBadge({ originCountry, detailed = false, dutyEstimateDisplay }: { originCountry?: string | null; detailed?: boolean; dutyEstimateDisplay?: string }) {
  const [destination, setDestination] = useState<CountryCode | null>(null);
  useEffect(() => {
    const update = (event?: Event) => {
      const detail = (event as CustomEvent<{ country?: string }> | undefined)?.detail;
      setDestination(detail?.country && isCountryCode(detail.country) ? detail.country : getSavedCountry());
    };
    update();
    window.addEventListener("astra:region-change", update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener("astra:region-change", update);
      window.removeEventListener("storage", update);
    };
  }, []);

  const originCode = originCountry ?? null;
  if (!destination || !isCountryCode(originCode) || destination === originCode) return null;
  const origin = getCountry(originCode);
  const buyer = getCountry(destination);
  const eta = shippingEta(originCode, destination);
  return detailed ? (
    <div className="mt-3 flex items-start gap-2 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3 text-xs">
      <Globe2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
      <div>
        <p className="font-semibold text-cyan-100">International shipping available</p>
        <p className="mt-1 text-ink-300">{origin.name} to {buyer.name}: {eta}</p>
        <p className="mt-1 text-ink-500">Indicative customs &amp; import duty planning estimate: {dutyEstimateDisplay ?? "unavailable without item price"} (10% allowance).</p>
        <p className="mt-1 text-[10px] text-ink-500">Advisory only. Actual charges depend on the destination customs authority and product HS code; this estimate is not included in checkout or charged by Astra.</p>
        <p className="mt-1 text-[10px] text-ink-500">ETA is indicative; availability and delivery timing are confirmed separately.</p>
      </div>
    </div>
  ) : (
    <span className="absolute bottom-2 left-2 z-10 inline-flex max-w-[calc(100%-1rem)] items-center gap-1 truncate rounded-full border border-cyan-200/20 bg-slate-950/85 px-2 py-1 text-[9px] font-semibold text-cyan-100 shadow-sm backdrop-blur">
      <Globe2 className="h-3 w-3 shrink-0" /> Intl · {origin.code}→{buyer.code} · {eta}
    </span>
  );
}

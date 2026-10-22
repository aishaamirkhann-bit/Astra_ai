"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Info, ShieldCheck, X } from "lucide-react";
import { getProductTrustScore, type TrustScore } from "@/lib/api";

export default function TrustBadgeCard({ productId }: { productId: string }) {
  const [trust, setTrust] = useState<TrustScore | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let active = true;
    void getProductTrustScore(productId).then((result) => { if (active) setTrust(result); }).catch(() => undefined);
    return () => { active = false; };
  }, [productId]);

  if (!trust) return null;
  const sections = [
    { title: "Review patterns", score: trust.evidence.reviews.score, available: trust.evidence.reviews.available, lines: trust.evidence.reviews.highlights },
    { title: "Buyer photos", score: trust.evidence.photos.score, available: trust.evidence.photos.available, lines: trust.evidence.photos.highlights },
    { title: "Seller record", score: trust.evidence.seller.score, available: trust.evidence.seller.available, lines: [trust.evidence.seller.verified ? "Seller identity marked verified" : "Seller identity not verified"] },
  ];
  return <>
    <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" className="mt-3 flex w-full items-center justify-between gap-3 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3 text-left hover:bg-cyan-400/10">
      <span className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 shrink-0 text-cyan-300" /><span><span className="block text-xs font-semibold text-ink-100">{trust.badge}</span><span className="mt-0.5 block text-[10px] text-ink-500">{trust.confidence === "low" ? "Limited review/photo evidence · tap for details" : "Trust signals · tap for breakdown"}</span></span></span>
      <Info className="h-4 w-4 shrink-0 text-ink-500" />
    </button>
    {open && <div className="fixed inset-0 z-[95] grid place-items-center bg-slate-950/75 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="trust-badge-title" className="glass w-full max-w-lg rounded-2xl border border-base-600 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2"><BadgeCheck className="h-5 w-5 text-cyan-300" /><div><h2 id="trust-badge-title" className="text-sm font-bold text-ink-100">Astra trust breakdown</h2><p className="mt-0.5 text-[10px] text-ink-500">{trust.badge} · advisory only</p></div></div><button type="button" aria-label="Close trust breakdown" onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-ink-400 hover:bg-base-700"><X className="h-4 w-4" /></button></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">{sections.map((section) => <article key={section.title} className="rounded-xl border border-base-700 bg-base-900/70 p-3"><div className="flex items-center justify-between gap-2"><h3 className="text-[10px] font-semibold text-ink-200">{section.title}</h3><span className="text-[10px] font-bold text-cyan-300">{section.available ? `${section.score}%` : "N/A"}</span></div><ul className="mt-2 space-y-1">{section.lines.map((line) => <li key={line} className="text-[9px] leading-relaxed text-ink-500">{line}</li>)}</ul></article>)}</div>
        <p className="mt-4 rounded-lg bg-amber-300/5 p-3 text-[10px] leading-relaxed text-amber-100/80">{trust.evidence.reviews.count === 0 && trust.evidence.photos.count === 0 ? "Review samples and buyer photos are not stored for this listing, so the percentage is a preliminary seller trust indicator—not a claim that reviews or images were verified." : "Automated indicators can be wrong. Use this score as buyer information, not as a guarantee of authenticity."} It does not change the listing, price, or checkout.</p>
      </section>
    </div>}
  </>;
}

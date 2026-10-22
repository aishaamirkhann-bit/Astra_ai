"use client";

import { useEffect, useState } from "react";
import CrossBorderShippingBadge from "@/components/CrossBorderShippingBadge";
import CatalogProductImage from "@/components/CatalogProductImage";
import { getBundleAdvisory, getOutfitRecommendations, type BundleOffer, type OutfitRecommendations } from "@/lib/api";

const money = (amount: number) => `Rs. ${Math.round(amount).toLocaleString("en-PK")}`;

export default function OutfitStylistCard({ productId }: { productId: string }) {
  const [recommendations, setRecommendations] = useState<OutfitRecommendations | null>(null);
  const [offer, setOffer] = useState<BundleOffer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void getOutfitRecommendations(productId).then((data) => { if (active) setRecommendations(data); })
      .catch(() => { if (active) setError("Outfit suggestions are unavailable right now."); });
    return () => { active = false; };
  }, [productId]);

  async function requestBundle(items: NonNullable<OutfitRecommendations["outfits"][number]["items"]>) {
    setLoading(true); setError(""); setOffer(null);
    try {
      const quote = await getBundleAdvisory(items.map(({ product }) => ({ product_id: product.id, quantity: 1 })));
      setOffer(quote);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Bundle estimate is unavailable."); }
    finally { setLoading(false); }
  }

  const outfit = recommendations?.outfits[0];
  return <section aria-label="AI outfit stylist" className="glass mt-5 rounded-xl2 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-300">Live Outfit Stylist</p><h2 className="mt-1 font-display text-base font-bold text-ink-100">Complete the look</h2><p className="mt-1 text-[10px] text-ink-500">Catalogue based style suggestions. Prices shown are estimates.</p></div>
      {outfit && <span className="rounded-full bg-violet-400/10 px-3 py-1.5 text-[10px] font-semibold text-violet-200">Estimated look · {money(outfit.estimated_total)}</span>}
    </div>
    {error && <p role="alert" className="mt-3 text-xs text-rose-400">{error}</p>}
    {!recommendations && !error && <p className="mt-4 text-xs text-ink-500">Finding complementary pieces…</p>}
    {recommendations && !outfit && <p className="mt-4 text-xs text-ink-500">{recommendations.message}</p>}
    {outfit && <>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{outfit.items.map(({ slot, product, reasons }) => <li key={product.id} className="overflow-hidden rounded-xl border border-base-700 bg-base-900/70">
        <div className="flex gap-3 p-3"><div className="relative h-20 w-16 shrink-0 overflow-hidden rounded-lg bg-base-800"><CatalogProductImage src={product.image_url} title={`${product.title} ${product.color}`} category={product.category} className="h-full w-full object-cover" /><CrossBorderShippingBadge originCountry={product.origin_country} /></div><div className="min-w-0"><span className="text-[9px] font-semibold uppercase tracking-wide text-cyan-300">{slot}</span><p className="mt-1 line-clamp-2 text-xs font-semibold text-white">{product.title}</p><p className="mt-1 text-[10px] text-ink-300">{money(product.price)}</p>{reasons.map((reason) => <p key={reason} className="mt-1 text-[9px] text-ink-500">{reason}</p>)}</div></div>
      </li>)}</ul>
      <button type="button" disabled={loading} onClick={() => void requestBundle(outfit.items)} className="mt-4 rounded-lg bg-astra-gradient px-4 py-2.5 text-[11px] font-bold text-white disabled:opacity-50">{loading ? "Preparing advisory offer…" : "Explore outfit bundle"}</button>
      {offer && <div className="mt-3 rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-3"><p className="text-xs font-semibold text-emerald-200">Advisory bundle: {money(offer.offer_total)} · estimated savings {money(offer.estimated_savings)}</p><p className="mt-1 text-[10px] text-ink-400">{offer.message} This does not add items to your cart or start checkout.</p></div>}
    </>}
  </section>;
}

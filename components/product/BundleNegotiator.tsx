"use client";

import { useEffect, useMemo, useState } from "react";
import { getBundleAdvisory, getBundleProductCandidates, type BundleOffer, type BundleProductCandidate } from "@/lib/api";

export default function BundleNegotiator({ initialProductId }: { initialProductId: string }) {
  const [products, setProducts] = useState<BundleProductCandidate[]>([]);
  const [selected, setSelected] = useState<Record<string, number>>({ [initialProductId]: 1 });
  const [addingId, setAddingId] = useState("");
  const [offer, setOffer] = useState<BundleOffer | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { void getBundleProductCandidates().then(setProducts).catch(() => setProducts([])); }, []);
  const selectedRows = useMemo(() => products.filter((product) => product.id in selected), [products, selected]);

  function addProduct() {
    if (!addingId) return;
    setSelected((current) => ({ ...current, [addingId]: current[addingId] ?? 1 }));
    setAddingId("");
    setOffer(null);
    setReviewed(false);
  }

  async function quoteBundle() {
    setBusy(true); setError(""); setOffer(null); setReviewed(false);
    try {
      const quote = await getBundleAdvisory(selectedRows.map((product) => ({ product_id: product.id, quantity: selected[product.id] })));
      setOffer(quote);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Bundle estimate is unavailable.");
    } finally { setBusy(false); }
  }

  return <section className="glass mt-5 rounded-xl2 p-5" aria-label="Multi-item bundle estimate">
    <h2 className="font-display text-sm font-bold text-ink-100">Smart bundle estimate</h2>
    <p className="mt-1 text-[10px] text-ink-500">Ask for a multi-item offer. Each line stays at or above its seller-set minimum.</p>
    <div className="mt-3 flex gap-2">
      <select aria-label="Add product to bundle" value={addingId} onChange={(event) => setAddingId(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100">
        <option value="">Choose another product</option>
        {products.filter((product) => !(product.id in selected) && (product.stock_count ?? 0) > 0).map((product) => <option key={product.id} value={product.id}>{product.title} · Rs. {product.price.toLocaleString()}</option>)}
      </select>
      <button type="button" onClick={addProduct} disabled={!addingId} className="rounded-lg border border-base-600 px-3 text-xs text-ink-200 disabled:opacity-40">Add</button>
    </div>
    <ul className="mt-3 grid gap-2 sm:grid-cols-2">{selectedRows.map((product) => <li key={product.id} className="flex items-center justify-between gap-2 rounded-lg bg-base-900 p-2.5 text-[10px] text-ink-300">
      <span className="min-w-0 truncate">{product.title}</span>
      <span className="flex items-center gap-2"><span>Rs. {product.price.toLocaleString()}</span><input aria-label={`Quantity for ${product.title}`} type="number" min="1" max={product.stock_count ?? 1} value={selected[product.id]} onChange={(event) => { setSelected((current) => ({ ...current, [product.id]: Math.max(1, Number(event.target.value) || 1) })); setOffer(null); setReviewed(false); }} className="w-14 rounded border border-base-600 bg-base-800 px-1.5 py-1 text-center" /></span>
    </li>)}</ul>
    <button type="button" onClick={() => void quoteBundle()} disabled={busy || selectedRows.length < 2} className="mt-3 rounded-lg bg-astra-gradient px-4 py-2 text-[11px] font-bold text-white disabled:opacity-50">{busy ? "Calculating advisory…" : "Get bundle estimate"}</button>
    {error && <p role="alert" className="mt-2 text-[10px] text-rose-400">{error}</p>}
    {offer && <div className="mt-4 rounded-xl border border-violet-400/20 bg-base-900/70 p-3">
      <ul className="grid gap-1.5">{offer.items.map((line) => <li key={line.product_id} className="flex justify-between gap-2 text-[10px] text-ink-300"><span>{line.title} × {line.quantity} · floor Rs. {line.seller_floor.toLocaleString()}</span><span>Rs. {line.line_total.toLocaleString()}</span></li>)}</ul>
      <p className="mt-3 flex justify-between border-t border-base-700 pt-2 text-xs font-bold text-ink-100"><span>Advisory total · saves Rs. {offer.estimated_savings.toLocaleString()}</span><span>Rs. {offer.offer_total.toLocaleString()}</span></p>
      <p className="mt-2 text-[10px] text-ink-500">Non-binding quote. It will not change cart prices or start checkout.</p>
      <button type="button" onClick={() => setReviewed(true)} className="mt-3 rounded-lg border border-violet-400/40 px-3 py-2 text-[10px] font-semibold text-violet-200">{reviewed ? "Offer reviewed" : "I reviewed this advisory offer"}</button>
      {reviewed && <p role="status" className="mt-2 text-[10px] text-emerald-300">Review recorded in this page. Any purchase still uses the standard checkout total and explicit financial consent.</p>}
    </div>}
  </section>;
}

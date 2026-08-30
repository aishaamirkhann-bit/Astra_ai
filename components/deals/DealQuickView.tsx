"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, CheckCircle2, Minus, Plus, ShieldCheck, ShoppingBag, Sparkles, Undo2, X, Zap } from "lucide-react";
import type { DealDetail } from "@/lib/types";

function TrustBar({ label, value, weight }: { label: string; value: number; weight: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-[10px] text-ink-500"><span>{label} · {weight}</span><span className="font-mono text-ink-100">{value}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-base-700"><motion.div initial={{ width: 0 }} animate={{ width: `${value}%` }} className="h-full rounded-full bg-astra-gradient" /></div>
    </div>
  );
}

function PriceChart({ deal }: { deal: DealDetail }) {
  const values = deal.price_history.flatMap((point) => [point.listing_price, point.market_average]);
  const min = Math.min(...values) * 0.96;
  const max = Math.max(...values) * 1.03;
  const point = (value: number, index: number) => `${index * 33.33},${88 - ((value - min) / (max - min || 1)) * 72}`;
  const listing = deal.price_history.map((item, index) => point(item.listing_price, index)).join(" ");
  const market = deal.price_history.map((item, index) => point(item.market_average, index)).join(" ");
  return (
    <div className="rounded-xl border border-base-600/70 bg-base-900/60 p-3">
      <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold text-ink-100">30-day price intelligence</p><span className="text-[10px] text-emerald-500">Lowest now</span></div>
      <svg viewBox="0 0 100 94" className="h-28 w-full overflow-visible" role="img" aria-label="Listing price compared with market average">
        {[20, 42, 64, 86].map((y) => <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="currentColor" className="text-base-600" strokeWidth="0.5" />)}
        <polyline points={market} fill="none" stroke="#94a3b8" strokeDasharray="3 3" strokeWidth="1.4" />
        <motion.polyline points={listing} fill="none" stroke="#8b5cf6" strokeWidth="2.4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.7 }} />
        {deal.price_history.map((item, index) => <text key={item.label} x={index * 33.33} y="94" textAnchor={index === 0 ? "start" : index === 3 ? "end" : "middle"} fontSize="5" fill="currentColor" className="text-ink-500">{item.label}</text>)}
      </svg>
      <div className="flex gap-4 text-[9px] text-ink-500"><span><i className="mr-1 inline-block h-1.5 w-3 rounded bg-violet-500" />Listing</span><span><i className="mr-1 inline-block h-0.5 w-3 border-t border-dashed border-slate-400" />Market average</span></div>
    </div>
  );
}

export default function DealQuickView({
  deal,
  goalAllocation,
  onClose,
  onAction,
  busyAction,
  approval,
  busyApproval,
  onApproval,
}: {
  deal: DealDetail | null;
  goalAllocation: { goalId: number; amount: number } | null;
  onClose: () => void;
  onAction: (deal: DealDetail, action: "cart" | "reserve", selection: { quantity: number; size: string; color: string }) => void;
  busyAction: "cart" | "reserve" | null;
  approval: { orderRef: string; expiresAt: string; amount: number; status: "pending" | "approved" | "cancelled" } | null;
  busyApproval: boolean;
  onApproval: (action: "approve" | "cancel") => void;
}) {
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [size, setSize] = useState("");
  const [color, setColor] = useState("");
  const [quantity, setQuantity] = useState(1);

  useEffect(() => {
    if (!deal) return;
    setGalleryIndex(0); setSize(deal.sizes[0] ?? ""); setColor(deal.colors[0] ?? ""); setQuantity(1);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", closeOnEscape); };
  }, [deal, onClose]);

  const activeImage = useMemo(() => deal?.gallery[galleryIndex] ?? deal?.image, [deal, galleryIndex]);

  return (
    <AnimatePresence>
      {deal && (
        <motion.div className="fixed inset-0 z-50 flex justify-end bg-slate-950/65 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-labelledby="deal-dialog-title"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="scroll-thin h-full w-full max-w-5xl overflow-y-auto border-l border-base-600 bg-base-950 shadow-2xl"
          >
            <div className="sticky top-0 z-20 flex items-center justify-between border-b border-base-600 bg-base-950/90 px-5 py-4 backdrop-blur-xl">
              <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-astra-cyan">Astra verified quick view</p><h2 id="deal-dialog-title" className="font-display text-lg font-semibold text-ink-100">{deal.name}</h2></div>
              <button type="button" onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full bg-base-800 text-ink-300 hover:text-ink-100" aria-label="Close quick view"><X className="h-5 w-5" /></button>
            </div>

            <div className="grid gap-7 p-5 lg:grid-cols-[1.05fr_.95fr] lg:p-7">
              <div>
                <motion.div className="group relative aspect-square overflow-hidden rounded-xl2 bg-base-800" whileHover="hover">
                  <motion.img src={activeImage} alt={deal.name} className="h-full w-full object-cover" variants={{ hover: { scale: 1.35 } }} transition={{ duration: 0.35 }} />
                  <span className="absolute bottom-3 right-3 rounded-full bg-slate-950/75 px-2.5 py-1 text-[10px] text-white">Hover to zoom</span>
                </motion.div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {deal.gallery.map((image, index) => <button key={`${image}-${index}`} type="button" onClick={() => setGalleryIndex(index)} className={`aspect-video overflow-hidden rounded-lg border-2 ${galleryIndex === index ? "border-astra-indigo" : "border-transparent"}`}><img src={image} alt={`${deal.name} view ${index + 1}`} className="h-full w-full object-cover" /></button>)}
                </div>

                <div className="mt-5 space-y-3 rounded-xl2 border border-violet-500/20 bg-violet-500/5 p-4">
                  <div className="flex items-start justify-between gap-3"><div><p className="flex items-center gap-2 text-sm font-semibold text-ink-100"><ShieldCheck className="h-4 w-4 text-emerald-500" /> Full AI Trust Analysis</p><p className="mt-1 text-[10px] text-ink-500">Weighted score · only listings at 75+ qualify</p></div><span className="font-display text-2xl font-bold text-emerald-500">{deal.trust.overall}</span></div>
                  <TrustBar label="Seller fulfillment" value={deal.trust.seller_fulfillment} weight="40%" />
                  <TrustBar label="Authenticity sentiment" value={deal.trust.authenticity_sentiment} weight="40%" />
                  <TrustBar label="Price stability" value={deal.trust.price_stability} weight="20%" />
                  <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 p-2.5 text-[10px] text-emerald-600 dark:text-emerald-300"><CheckCircle2 className="h-4 w-4 shrink-0" /> {deal.trust.summary}</div>
                </div>
                <div className="mt-4"><PriceChart deal={deal} /></div>
              </div>

              <div className="lg:sticky lg:top-24 lg:self-start">
                {goalAllocation && <div className="mb-4 rounded-xl border border-cyan-500/25 bg-cyan-500/5 p-3"><p className="text-xs font-semibold text-ink-100">Goal funds pre-filled</p><p className="mt-1 text-[10px] text-ink-500">Rs. {goalAllocation.amount.toLocaleString()} allocated from shopping goal #{goalAllocation.goalId}. Final application remains subject to approval.</p></div>}
                <div className="flex items-center gap-2"><span className="rounded-full bg-rose-500 px-2.5 py-1 text-[10px] font-bold text-white">{deal.discount_percent}% OFF</span><span className="text-xs text-ink-500">Save {deal.savings_display}</span></div>
                <div className="mt-3 flex items-end gap-3"><p className="font-display text-3xl font-bold text-ink-100">{deal.price_display}</p><p className="pb-1 text-sm text-ink-500 line-through">{deal.market_price_display}</p></div>
                <p className="mt-4 text-sm leading-6 text-ink-300">{deal.description}</p>
                <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-base-800 p-3 text-[11px]"><div><p className="text-ink-500">Verified seller</p><p className="mt-1 font-semibold text-ink-100">{deal.seller}</p></div><div><p className="text-ink-500">Live inventory</p><p className="mt-1 font-semibold text-rose-500">Only {deal.stock_remaining} left</p></div></div>

                <div className="mt-6"><p className="mb-2 text-xs font-semibold text-ink-100">Variant / Size</p><div className="flex flex-wrap gap-2">{deal.sizes.map((item) => <button type="button" key={item} onClick={() => setSize(item)} className={`rounded-lg border px-3 py-2 text-xs ${size === item ? "border-astra-indigo bg-astra-indigo/10 text-ink-100" : "border-base-600 text-ink-500"}`}>{item}</button>)}</div></div>
                <div className="mt-5"><p className="mb-2 text-xs font-semibold text-ink-100">Color</p><div className="flex flex-wrap gap-2">{deal.colors.map((item) => <button type="button" key={item} onClick={() => setColor(item)} className={`rounded-lg border px-3 py-2 text-xs ${color === item ? "border-astra-cyan bg-astra-cyan/10 text-ink-100" : "border-base-600 text-ink-500"}`}>{item}</button>)}</div></div>
                <div className="mt-5"><p className="mb-2 text-xs font-semibold text-ink-100">Quantity</p><div className="inline-flex items-center rounded-lg border border-base-600"><button type="button" onClick={() => setQuantity((value) => Math.max(1, value - 1))} className="p-2 text-ink-300" aria-label="Decrease quantity"><Minus className="h-4 w-4" /></button><span className="w-10 text-center font-mono text-sm text-ink-100">{quantity}</span><button type="button" onClick={() => setQuantity((value) => Math.min(deal.stock_remaining, value + 1))} className="p-2 text-ink-300" aria-label="Increase quantity"><Plus className="h-4 w-4" /></button></div></div>

                <div className="mt-7 space-y-3">
                  <button type="button" disabled={busyAction !== null || deal.stock_remaining < 1 || approval?.status === "pending" || approval?.status === "approved"} onClick={() => onAction(deal, "reserve", { quantity, size, color })} className="flex w-full items-center justify-center gap-2 rounded-xl bg-astra-gradient px-4 py-3.5 text-sm font-bold text-white shadow-glow disabled:opacity-60"><Zap className="h-4 w-4" /> {busyAction === "reserve" ? "Reserving deal…" : approval?.status === "pending" ? "Awaiting Approval" : "Direct Checkout / Buy Now"}</button>
                  <button type="button" disabled={busyAction !== null || deal.stock_remaining < 1} onClick={() => onAction(deal, "cart", { quantity, size, color })} className="flex w-full items-center justify-center gap-2 rounded-xl border border-base-600 bg-base-800 px-4 py-3 text-sm font-semibold text-ink-100 hover:border-astra-indigo disabled:opacity-60"><ShoppingBag className="h-4 w-4" /> {busyAction === "cart" ? "Adding…" : "Add to Cart"}</button>
                </div>
                {approval && (
                  <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                    <p className="text-xs font-semibold text-ink-100">Human approval · {approval.orderRef}</p>
                    {approval.status === "pending" ? (
                      <>
                        <p className="mt-1 text-[10px] text-ink-500">Inventory is reserved until {new Date(approval.expiresAt).toLocaleTimeString()}.</p>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          <button type="button" disabled={busyApproval} onClick={() => onApproval("approve")} className="flex items-center justify-center gap-1.5 rounded-lg bg-astra-gradient px-3 py-2.5 text-xs font-semibold text-white disabled:opacity-60"><Check className="h-3.5 w-3.5" /> Approve</button>
                          <button type="button" disabled={busyApproval} onClick={() => onApproval("cancel")} className="flex items-center justify-center gap-1.5 rounded-lg border border-rose-500/30 px-3 py-2.5 text-xs font-semibold text-rose-500 disabled:opacity-60"><Undo2 className="h-3.5 w-3.5" /> Cancel</button>
                        </div>
                      </>
                    ) : <p className={`mt-2 text-xs font-semibold ${approval.status === "approved" ? "text-emerald-500" : "text-rose-500"}`}>{approval.status === "approved" ? "Transaction approved. You can reverse it from Orders during the grace window." : "Order cancelled and stock restored."}</p>}
                  </div>
                )}
                <p className="mt-3 flex items-center justify-center gap-1.5 text-center text-[10px] text-ink-500"><Sparkles className="h-3 w-3 text-violet-500" /> No redirect · Astra approval stays in this drawer</p>
              </div>
            </div>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

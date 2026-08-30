"use client";

import { motion } from "framer-motion";
import { Clock3, ShieldCheck, ShoppingCart, Sparkles, Star } from "lucide-react";
import type { DealOut } from "@/lib/types";

const badgeStyles: Record<DealOut["tag"], string> = {
  Bestseller: "bg-violet-600 text-white",
  New: "bg-blue-500 text-white",
  "Mega Deal": "bg-rose-500 text-white",
};

function urgencyCopy(deal: DealOut) {
  if (deal.stock_remaining <= 3) return `Only ${deal.stock_remaining} left at this price!`;
  if (deal.expires_at) return "Flash price ends soon";
  return `${deal.stock_remaining} units verified at this price`;
}

export default function DealCard({
  deal,
  onOpen,
  onQuickAdd,
  quickAdding,
}: {
  deal: DealOut;
  onOpen: (deal: DealOut) => void;
  onQuickAdd: (deal: DealOut) => void;
  quickAdding: boolean;
}) {
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      whileHover={{ y: -5 }}
      transition={{ duration: 0.24 }}
      className="group glass relative overflow-hidden rounded-xl2"
    >
      <button type="button" onClick={() => onOpen(deal)} className="block w-full text-left" aria-label={`Quick view ${deal.name}`}>
        <div className="relative aspect-[4/3] overflow-hidden bg-base-700">
          <motion.img
            src={deal.image}
            alt={deal.name}
            className="h-full w-full object-cover"
            whileHover={{ scale: 1.07 }}
            transition={{ duration: 0.35 }}
          />
          <span className={`absolute left-3 top-3 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide shadow-lg ${badgeStyles[deal.tag]}`}>
            {deal.tag}
          </span>
          <div className="group/trust absolute right-3 top-3">
            <span className="flex items-center gap-1 rounded-full border border-white/20 bg-slate-950/85 px-2 py-1 text-[11px] font-bold text-emerald-300 shadow-lg backdrop-blur">
              <ShieldCheck className="h-3.5 w-3.5" /> {deal.trust.overall}
            </span>
            <div role="tooltip" className="pointer-events-none absolute right-0 top-9 z-20 w-64 translate-y-1 rounded-xl border border-white/10 bg-slate-950 p-3 text-left text-[10px] leading-5 text-slate-200 opacity-0 shadow-2xl transition group-hover/trust:translate-y-0 group-hover/trust:opacity-100 group-focus-within/trust:translate-y-0 group-focus-within/trust:opacity-100">
              <p className="font-semibold text-white">AI Trust Score breakdown</p>
              <p>Seller fulfillment: {deal.trust.seller_fulfillment}%</p>
              <p>Authenticity sentiment: {deal.trust.authenticity_sentiment}%</p>
              <p>Price stability: {deal.trust.price_stability}%</p>
            </div>
          </div>
          <div className="absolute inset-x-3 bottom-3 translate-y-3 opacity-0 transition duration-200 group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100">
            <span className="flex items-center justify-center gap-2 rounded-xl bg-slate-950/90 px-3 py-2 text-xs font-semibold text-white backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-violet-300" /> View AI deal analysis
            </span>
          </div>
        </div>

        <div className="p-4">
          <div className="mb-2 flex items-center justify-between gap-2 text-[10px] text-ink-500">
            <span>{deal.category}</span>
            <span className="flex items-center gap-1"><Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {deal.rating} ({deal.total_reviews})</span>
          </div>
          <h2 className="line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-ink-100">{deal.name}</h2>
          <p className="mt-1 truncate text-[11px] text-ink-500">Verified by Astra · {deal.seller}</p>

          <div className="mt-4 flex flex-wrap items-end gap-x-2 gap-y-1">
            <span className="font-display text-lg font-bold text-ink-100">{deal.price_display}</span>
            <span className="pb-0.5 text-[11px] text-ink-500 line-through">{deal.market_price_display}</span>
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-300">{deal.discount_percent}% OFF</span>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-[10px] font-medium text-rose-500">
            <Clock3 className="h-3.5 w-3.5" /> {urgencyCopy(deal)}
          </div>
        </div>
      </button>

      <div className="px-4 pb-4">
        <button
          type="button"
          onClick={() => onQuickAdd(deal)}
          disabled={quickAdding || deal.stock_remaining < 1}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-astra-gradient px-4 py-2.5 text-xs font-semibold text-white shadow-glow transition hover:brightness-110 active:scale-[0.98]"
        >
          <ShoppingCart className="h-4 w-4" /> {quickAdding ? "Adding…" : deal.stock_remaining < 1 ? "Out of stock" : "Quick add to cart"}
        </button>
      </div>
    </motion.article>
  );
}

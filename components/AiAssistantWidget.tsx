"use client";

import Link from "next/link";
import { Sparkles, Star, ShieldCheck, ShoppingCart, X } from "lucide-react";
import { useState } from "react";
import { PRODUCTS } from "@/lib/mockData";

export default function AiAssistantWidget() {
  const featured = PRODUCTS[0];
  const [open, setOpen] = useState(true);
  if (!open) return null;

  return (
    <section className="glass glass-hover rounded-xl2 p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-astra-violet" />
          <h2 className="font-display text-sm font-semibold text-ink-100">AI Assistant</h2>
        </div>
        <button
          onClick={() => setOpen(false)}
          aria-label="Dismiss assistant suggestion"
          className="text-ink-500 hover:text-ink-100"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="mb-3 rounded-lg bg-base-800 px-3 py-2 text-xs text-ink-300">
        Yeh product aapke liye best match hai:
      </p>

      <Link href={`/product/${featured.slug}`} className="flex gap-3">
        <div
          className="photo-frame h-16 w-16 shrink-0 rounded-lg"
          style={{ backgroundImage: `url(${featured.image})` }}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink-100">{featured.name}</p>
          <div className="mt-0.5 flex items-center gap-1 text-[11px] text-ink-500">
            <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
            {featured.rating}
          </div>
          <p className="mt-1 font-display text-sm font-semibold text-ink-100">{featured.price}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
              Fits your budget
            </span>
            <span className="flex items-center gap-0.5 rounded-full bg-astra-gradient-soft px-2 py-0.5 text-[10px] font-medium text-ink-100">
              <ShieldCheck className="h-2.5 w-2.5" /> Verified Seller
            </span>
          </div>
        </div>
      </Link>

      <button className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90">
        <ShoppingCart className="h-3.5 w-3.5" /> Add to Cart
      </button>
    </section>
  );
}

"use client";

import Link from "next/link";
import { Star, Heart, ShoppingCart, ShieldCheck } from "lucide-react";
import type { Product } from "@/lib/types";

export default function ProductGrid({ products }: { products: Product[] }) {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-ink-100">Recommended For You</h2>
        <Link href="/explore" className="text-[11px] font-medium text-ink-500 hover:text-ink-100">
          View all
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {products.map((p) => (
          <Link
            key={p.slug}
            href={`/product/${p.slug}`}
            className="glass glass-hover group block rounded-xl2 p-3"
          >
            <div
              className="photo-frame relative mb-3 aspect-square rounded-lg"
              style={{ backgroundImage: `url(${p.image})` }}
            >
              {p.tag && (
                <span className="absolute left-2 top-2 rounded-full bg-astra-gradient px-2 py-0.5 text-[9px] font-semibold text-white">
                  {p.tag}
                </span>
              )}
              <button
                aria-label={`Save ${p.name}`}
                onClick={(e) => e.preventDefault()}
                className="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-base-900/70 text-white opacity-0 transition-opacity group-hover:opacity-100 hover:text-signal-reject"
              >
                <Heart className="h-3 w-3" />
              </button>
            </div>

            <p className="truncate text-xs font-medium text-ink-100">{p.name}</p>
            <div className="mt-1 flex items-center justify-between">
              <div className="flex items-center gap-1 text-[10px] text-ink-500">
                <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
                {p.rating}
              </div>
              <div className="flex items-center gap-0.5 text-[10px] text-signal-good">
                <ShieldCheck className="h-3 w-3" />
                {p.trust}
              </div>
            </div>
            <p className="mt-1 font-display text-sm font-semibold text-ink-100">{p.price_display}</p>

            <span
              className={[
                "mt-2 inline-block rounded-full px-2 py-0.5 text-[9px] font-medium",
                p.fit === "Fits your budget"
                  ? "bg-signal-good/10 text-signal-good"
                  : "bg-signal-hold/10 text-signal-hold",
              ].join(" ")}
            >
              {p.fit}
            </span>

            <button
              onClick={(e) => e.preventDefault()}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-base-600 py-1.5 text-[11px] font-medium text-ink-300 transition-colors hover:border-astra-indigo/50 hover:text-ink-100"
            >
              <ShoppingCart className="h-3 w-3" /> Add
            </button>
          </Link>
        ))}
      </div>
    </section>
  );
}

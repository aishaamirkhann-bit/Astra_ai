"use client";

import Link from "next/link";
import { Sparkles, Star, ShieldCheck, ShoppingCart, X, Check } from "lucide-react";
import { useEffect, useState } from "react";
import type { AiAssistantSuggestion } from "@/lib/types";
import { addToCart } from "@/lib/api";

export default function AiAssistantWidget({ suggestion }: { suggestion: AiAssistantSuggestion }) {
  const [open, setOpen] = useState(true);
  const [cartState, setCartState] = useState<"idle" | "loading" | "added" | "error">("idle");
  useEffect(() => { setOpen(window.sessionStorage.getItem("astra:assistant-dismissed") !== suggestion.product.slug); }, [suggestion.product.slug]);
  if (!open) return null;

  const { product } = suggestion;

  async function handleAddToCart() {
    setCartState("loading");
    try {
      await addToCart(product.slug);
      setCartState("added");
    } catch {
      setCartState("error");
    }
  }

  return (
    <section className="glass glass-hover rounded-xl2 p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-astra-violet" />
          <h2 className="font-display text-sm font-semibold text-ink-100">AI Assistant</h2>
        </div>
        <button
          onClick={() => { window.sessionStorage.setItem("astra:assistant-dismissed", product.slug); setOpen(false); }}
          aria-label="Dismiss assistant suggestion"
          className="text-ink-500 hover:text-ink-100"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <p className="mb-3 rounded-lg bg-base-800 px-3 py-2 text-xs text-ink-300">
        {suggestion.message}
      </p>

      <Link href={`/product/${product.slug}`} className="flex gap-3">
        <div
          className="photo-frame h-16 w-16 shrink-0 rounded-lg"
          style={{ backgroundImage: `url(${product.image})` }}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink-100">{product.name}</p>
          <div className="mt-0.5 flex items-center gap-1 text-[11px] text-ink-500">
            <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
            {product.rating}
          </div>
          <p className="mt-1 font-display text-sm font-semibold text-ink-100">{product.price_display}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {suggestion.fits_budget && (
              <span className="rounded-full bg-signal-good/10 px-2 py-0.5 text-[10px] font-medium text-signal-good">
                Fits your budget
              </span>
            )}
            {suggestion.verified_seller && (
              <span className="flex items-center gap-0.5 rounded-full bg-astra-gradient-soft px-2 py-0.5 text-[10px] font-medium text-ink-100">
                <ShieldCheck className="h-2.5 w-2.5" /> Verified Seller
              </span>
            )}
          </div>
        </div>
      </Link>

      <button
        onClick={handleAddToCart}
        disabled={cartState === "loading" || cartState === "added"}
        className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-70"
      >
        {cartState === "added" ? (
          <>
            <Check className="h-3.5 w-3.5" /> Added to Cart
          </>
        ) : cartState === "error" ? (
          "Couldn't add — try again"
        ) : (
          <>
            <ShoppingCart className="h-3.5 w-3.5" /> {cartState === "loading" ? "Adding…" : "Add to Cart"}
          </>
        )}
      </button>
    </section>
  );
}

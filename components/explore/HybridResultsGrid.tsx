"use client";

import Link from "next/link";
import { Heart, Scale, SearchX, ShieldCheck, Star, X } from "lucide-react";
import { useEffect, useState } from "react";
export type ExploreProduct = {
  id: string;
  title: string;
  category: string;
  price: number;
  formatted_price: string;
  rating: number;
  total_reviews: number;
  seller_name: string;
  is_verified_seller: boolean;
  badge: string | null;
  image_url: string;
  semantic_tags: string[];
  trust: number;
};

export default function HybridResultsGrid({
  products,
  totalResults,
  sortBy,
  onSortChange,
  loading,
}: {
  products: ExploreProduct[];
  totalResults: number;
  sortBy: string;
  onSortChange: (value: string) => void;
  loading: boolean;
}) {
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]);

  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem("astra:saved-products") || "[]");
      if (Array.isArray(saved)) setSavedIds(saved);
    } catch { /* Ignore corrupted local data. */ }
  }, []);

  const toggleSaved = (id: string) => {
    setSavedIds((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      window.localStorage.setItem("astra:saved-products", JSON.stringify(next));
      return next;
    });
  };
  const toggleCompare = (id: string) => {
    setCompareIds((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 2 ? [...current, id] : [current[1], id]);
  };
  const comparedProducts = products.filter((product) => compareIds.includes(product.id));

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs text-ink-500">
          <span className="font-semibold text-ink-100">{totalResults}</span> results ·
          blending keyword + semantic match
        </p>
        <select value={sortBy} onChange={(event) => onSortChange(event.target.value)} className="rounded-lg border border-base-600 bg-base-800 px-2.5 py-1.5 text-[11px] text-ink-300">
          <option value="most_relevant">Most relevant</option>
          <option value="price_low_high">Price: low to high</option>
          <option value="price_high_low">Price: high to low</option>
          <option value="rating">Rating</option>
        </select>
      </div>

      {comparedProducts.length > 0 && <div className="glass mb-4 rounded-xl2 p-4">
        <div className="flex items-center justify-between gap-3"><p className="flex items-center gap-1.5 text-xs font-semibold text-ink-100"><Scale className="h-4 w-4 text-astra-cyan" /> Compare products {comparedProducts.length}/2</p><button type="button" onClick={() => setCompareIds([])} className="text-xs text-ink-500 hover:text-ink-100">Clear</button></div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">{comparedProducts.map((product) => <div key={product.id} className="rounded-lg border border-base-600 bg-base-800/50 p-3"><div className="flex items-start justify-between gap-2"><p className="text-xs font-medium text-ink-100">{product.title}</p><button type="button" onClick={() => toggleCompare(product.id)} aria-label={`Remove ${product.title} from comparison`} className="text-ink-500 hover:text-ink-100"><X className="h-3.5 w-3.5" /></button></div><div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-ink-500"><span>Price<br /><b className="text-ink-100">{product.formatted_price}</b></span><span>Rating<br /><b className="text-ink-100">{product.rating}/5</b></span><span>Trust<br /><b className="text-signal-good">{product.trust}%</b></span></div></div>)}</div>
      </div>}

      {loading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, index) => <div key={index} className="glass animate-pulse rounded-xl2 p-3"><div className="aspect-square rounded-lg bg-base-700" /><div className="mt-3 h-3 w-4/5 rounded bg-base-700" /><div className="mt-2 h-3 w-2/5 rounded bg-base-700" /></div>)}</div>
      ) : products.length === 0 ? (
        <div className="glass flex flex-col items-center gap-2 rounded-xl2 p-10 text-center">
          <SearchX className="h-6 w-6 text-ink-500" />
          <p className="text-sm font-medium text-ink-100">No matches yet</p>
          <p className="text-xs text-ink-500">Try a different search term, category, or a higher price cap.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {products.map((p) => (
            <Link
              key={p.id}
              href={`/product/${p.id}`}
              className="glass glass-hover block rounded-xl2 p-3"
            >
              <div
                className="photo-frame relative mb-3 aspect-square rounded-lg"
                style={{ backgroundImage: `url(${p.image_url})` }}
              >
                {p.badge && (
                  <span className="absolute left-2 top-2 rounded-full bg-astra-gradient px-2 py-0.5 text-[9px] font-semibold text-white">
                    {p.badge}
                  </span>
                )}
                <button type="button" onClick={(event) => { event.preventDefault(); toggleSaved(p.id); }} aria-label={savedIds.includes(p.id) ? `Remove ${p.title} from saved items` : `Save ${p.title}`} className={["absolute right-2 top-2 rounded-full border p-1.5 backdrop-blur transition", savedIds.includes(p.id) ? "border-signal-reject/40 bg-signal-reject/15 text-signal-reject" : "border-white/15 bg-base-950/50 text-white hover:border-astra-cyan/50 hover:text-astra-cyan"].join(" ")}><Heart className={savedIds.includes(p.id) ? "h-3.5 w-3.5 fill-current" : "h-3.5 w-3.5"} /></button>
              </div>
              <p className="truncate text-xs font-medium text-ink-100">{p.title}</p>
              <div className="mt-1 flex items-center justify-between">
                <div className="flex items-center gap-1 text-[10px] text-ink-500">
                  <Star className="h-3 w-3 fill-signal-hold text-signal-hold" />
                  {p.rating}
                </div>
                <div className="flex items-center gap-1 text-[10px] text-signal-good">
                  <ShieldCheck className="h-3 w-3" />
                  {p.is_verified_seller ? "Verified" : ""}
                </div>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-ink-500"><span>{p.semantic_tags.includes("Fast delivery") ? "Fast delivery" : "Delivery options"}</span><span className="font-medium text-signal-good">{p.trust}% trust</span></div>
              <p className="mt-1 font-display text-sm font-semibold text-ink-100">{p.formatted_price}</p>
              <p className="truncate text-[10px] text-ink-500">{p.seller_name} · {p.total_reviews.toLocaleString()} reviews</p>
              <button type="button" onClick={(event) => { event.preventDefault(); toggleCompare(p.id); }} className={["mt-3 inline-flex items-center gap-1 text-[10px] font-medium transition", compareIds.includes(p.id) ? "text-astra-cyan" : "text-ink-500 hover:text-ink-100"].join(" ")}><Scale className="h-3 w-3" /> {compareIds.includes(p.id) ? "Added to compare" : "Compare"}</button>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

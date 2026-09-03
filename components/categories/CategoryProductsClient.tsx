"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronLeft, ShieldCheck, Star } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Product = {
  id: string;
  title: string;
  category: string;
  price: number;
  formatted_price: string;
  rating: number;
  seller_name: string;
  is_verified_seller: boolean;
  badge: string | null;
  image_url: string;
};

export default function CategoryProductsClient({ categoryName }: { categoryName: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [minPrice, setMinPrice] = useState(0);
  const [maxPrice, setMaxPrice] = useState(500000);
  const [sortBy, setSortBy] = useState("most_relevant");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [minRating, setMinRating] = useState(0);
  const [page, setPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const filtersActive = minPrice !== 0 || maxPrice !== 500000 || sortBy !== "most_relevant" || verifiedOnly || minRating !== 0;
  const resetFilters = () => {
    setMinPrice(0);
    setMaxPrice(500000);
    setSortBy("most_relevant");
    setVerifiedOnly(false);
    setMinRating(0);
    setPage(1);
  };

  useEffect(() => {
    const slug = categoryName.toLowerCase().replace(" & ", "-").replaceAll(" ", "-");
    const params = new URLSearchParams({ min_price: String(minPrice), max_price: String(maxPrice), page: String(page), limit: "8", sort_by: sortBy, verified_only: String(verifiedOnly), min_rating: String(minRating) });
    setLoading(true);
    setError(null);
    fetch(`${API_URL}/api/v1/explore/categories/${slug}/products?${params}`)
      .then((response) => {
        if (!response.ok) throw new Error("Products unavailable");
        return response.json();
      })
      .then((payload: { items: Product[]; total_results: number; total_pages: number }) => {
        setProducts(payload.items);
        setTotalResults(payload.total_results);
        setTotalPages(payload.total_pages);
      })
      .catch(() => setError("Could not load products from the database."))
      .finally(() => setLoading(false));
  }, [categoryName, minPrice, maxPrice, page, sortBy, verifiedOnly, minRating]);

  return (
    <div>
      <Link href="/categories" className="mb-5 inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-100">
        <ChevronLeft className="h-3.5 w-3.5" /> All categories
      </Link>
      <div className="glass mb-5 grid gap-5 rounded-xl2 p-5 lg:grid-cols-[minmax(260px,1fr)_105px_105px_auto_auto] lg:items-end">
        <div>
          <p className="text-sm font-medium text-ink-100">Price Range: Rs. {minPrice.toLocaleString()} — Rs. {maxPrice.toLocaleString()}</p>
          <div className="relative mt-3 h-5">
            <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-base-600" />
            <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-astra-gradient" style={{ left: `${(minPrice / 500000) * 100}%`, right: `${100 - (maxPrice / 500000) * 100}%` }} />
            <input type="range" min="0" max="500000" step="5000" value={minPrice} onChange={(event) => { setMinPrice(Math.min(Number(event.target.value), maxPrice)); setPage(1); }} className="dual-range absolute inset-0 w-full" aria-label="Minimum price" />
            <input type="range" min="0" max="500000" step="5000" value={maxPrice} onChange={(event) => { setMaxPrice(Math.max(Number(event.target.value), minPrice)); setPage(1); }} className="dual-range dual-range-max absolute inset-0 w-full" aria-label="Maximum price" />
          </div>
        </div>
        <label className="text-xs font-medium text-ink-300">Min:
          <input type="number" min="0" max={maxPrice} step="5000" value={minPrice} onChange={(event) => { setMinPrice(Math.min(Number(event.target.value) || 0, maxPrice)); setPage(1); }} className="mt-2 block w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100 outline-none transition focus:border-astra-cyan" />
        </label>
        <label className="text-xs font-medium text-ink-300">Max:
          <input type="number" min={minPrice} max="500000" step="5000" value={maxPrice} onChange={(event) => { setMaxPrice(Math.max(Number(event.target.value) || minPrice, minPrice)); setPage(1); }} className="mt-2 block w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100 outline-none transition focus:border-astra-violet" />
        </label>
        <label className="text-xs font-medium text-ink-300">Sort by:
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }} className="mt-2 block min-w-52 rounded-lg border border-astra-cyan/30 bg-base-800 px-3 py-2.5 text-sm text-ink-100 outline-none transition focus:border-astra-cyan">
              <option value="most_relevant">Most relevant</option>
              <option value="price_low_high">Price: low to high</option>
            <option value="price_high_low">Price: high to low</option>
            <option value="rating">Rating</option>
          </select>
        </label>
        <div className="flex items-end justify-between gap-3 lg:flex-col lg:items-end">
          <p className="text-right text-xs whitespace-nowrap text-ink-500">Showing {totalResults} products</p>
          {filtersActive && <button type="button" onClick={resetFilters} className="text-xs font-medium text-astra-cyan transition hover:text-ink-100">Reset filters</button>}
        </div>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => { setVerifiedOnly((value) => !value); setPage(1); }} className={["rounded-full border px-3 py-1.5 text-xs font-medium transition", verifiedOnly ? "border-astra-cyan/50 bg-astra-cyan/10 text-astra-cyan" : "border-base-600 text-ink-500 hover:text-ink-100"].join(" ")}>Verified sellers only</button>
        {[4, 4.5].map((rating) => <button key={rating} type="button" onClick={() => { setMinRating((value) => value === rating ? 0 : rating); setPage(1); }} className={["rounded-full border px-3 py-1.5 text-xs font-medium transition", minRating === rating ? "border-astra-violet/50 bg-astra-violet/10 text-ink-100" : "border-base-600 text-ink-500 hover:text-ink-100"].join(" ")}>{rating}+ rating</button>)}
        {filtersActive && <span className="text-xs text-ink-500">Filters are applied</span>}
      </div>
      {error && <p className="mb-4 rounded-lg border border-signal-reject/30 bg-signal-reject/10 p-3 text-xs text-signal-reject">{error}</p>}
      {loading && <p className="text-sm text-ink-500">Loading products...</p>}
      {!loading && !error && products.length === 0 && <p className="text-sm text-ink-500">No products in this category yet.</p>}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {products.map((product) => (
          <Link key={product.id} href={`/product/${product.id}`} className="glass glass-hover group block rounded-xl2 p-3">
            <div className="photo-frame relative mb-3 aspect-square rounded-lg" style={{ backgroundImage: `url(${product.image_url})` }}>
              {product.badge && <span className="absolute left-2 top-2 rounded-full bg-astra-gradient px-2 py-0.5 text-[9px] font-semibold text-white">{product.badge}</span>}
            </div>
            <p className="truncate text-xs font-medium text-ink-100">{product.title}</p>
            <div className="mt-1 flex items-center justify-between text-[10px] text-ink-500">
              <span className="flex items-center gap-1"><Star className="h-3 w-3 fill-signal-hold text-signal-hold" />{product.rating}</span>
              {product.is_verified_seller && <span className="flex items-center gap-1 text-signal-good"><ShieldCheck className="h-3 w-3" />Verified</span>}
            </div>
            <p className="mt-1 font-display text-sm font-semibold text-ink-100">{product.formatted_price}</p>
            <p className="truncate text-[10px] text-ink-500">{product.seller_name}</p>
          </Link>
        ))}
      </div>
      {!loading && totalPages > 1 && <div className="mt-5 flex items-center justify-center gap-3"><button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-base-600 px-3 py-2 text-xs text-ink-300 disabled:opacity-40">Previous</button><span className="text-xs text-ink-500">Page {page} of {totalPages}</span><button type="button" disabled={page === totalPages} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-base-600 px-3 py-2 text-xs text-ink-300 disabled:opacity-40">Next</button></div>}
    </div>
  );
}

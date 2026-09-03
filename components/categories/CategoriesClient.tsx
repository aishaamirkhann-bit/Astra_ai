"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw, Sparkles } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CATEGORY_GRADIENTS: Record<string, string> = {
  Mobiles: "linear-gradient(135deg, rgba(34,211,238,0.25), rgba(59,130,246,0.10))",
  "Laptops & Computers": "linear-gradient(135deg, rgba(168,85,247,0.25), rgba(59,130,246,0.10))",
  "Audio & Wearables": "linear-gradient(135deg, rgba(56,189,248,0.25), rgba(14,165,233,0.10))",
  Jewelry: "linear-gradient(135deg, rgba(251,191,36,0.20), rgba(245,158,11,0.08))",
  "Clothing & Fashion": "linear-gradient(135deg, rgba(244,114,182,0.22), rgba(168,85,247,0.10))",
  "Makeup & Beauty": "linear-gradient(135deg, rgba(251,113,133,0.20), rgba(236,72,153,0.08))",
  "Home Appliances": "linear-gradient(135deg, rgba(16,185,129,0.20), rgba(45,212,191,0.08))",
  "Home & Living": "linear-gradient(135deg, rgba(250,204,21,0.18), rgba(34,197,94,0.08))",
};

type Category = { id: string; name: string; slug: string; product_count: number };

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  "Mobiles": "Phones, tablets & accessories",
  "Laptops": "Work, study & gaming laptops",
  "Audio & Wearables": "Sound, fitness & smart tech",
  "Jewelry": "Everyday and occasion pieces",
  "Clothing & Fashion": "Style picks for every day",
  "Makeup & Beauty": "Skincare and beauty essentials",
  "Home Appliances": "Reliable essentials for home",
  "Home & Living": "Furniture, décor & more",
};

export default function CategoriesClient() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetch(`${API_URL}/api/v1/explore/categories`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Category service unavailable");
        return response.json();
      })
      .then(setCategories)
      .catch((requestError) => {
        if ((requestError as Error).name !== "AbortError") setError("We could not load the catalogue right now.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [retryKey]);

  return (
    <div>
      {error && (
        <div className="mb-4 flex flex-col gap-3 rounded-xl border border-signal-reject/30 bg-signal-reject/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-signal-reject">{error} Please ensure the Astra backend is running, then try again.</p>
          <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-signal-reject/30 px-3 py-1.5 text-xs font-medium text-signal-reject transition hover:bg-signal-reject/10">
            <RefreshCw className="h-3.5 w-3.5" /> Retry
          </button>
        </div>
      )}
      {loading && <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, index) => <div key={index} className="glass animate-pulse overflow-hidden rounded-xl2"><div className="aspect-[4/3] bg-base-700" /><div className="space-y-2 p-4"><div className="h-3 w-3/4 rounded bg-base-700" /><div className="h-2.5 w-1/2 rounded bg-base-700" /></div></div>)}</div>}
      {!loading && !error && categories.length === 0 && (
        <div className="glass flex flex-col items-center rounded-xl2 px-5 py-14 text-center">
          <Sparkles className="mb-3 h-6 w-6 text-astra-cyan" />
          <p className="text-sm font-semibold text-ink-100">Categories are being prepared</p>
          <p className="mt-1 max-w-sm text-xs text-ink-500">Please refresh in a moment to see the latest Astra catalogue.</p>
          <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="mt-4 rounded-lg border border-base-600 px-3 py-2 text-xs text-ink-300 transition hover:border-astra-cyan/50 hover:text-ink-100">Refresh catalogue</button>
        </div>
      )}
      {!loading && !error && categories.length > 0 && <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
        {categories.map((category) => {
          const background = CATEGORY_GRADIENTS[category.name] ?? "linear-gradient(135deg, rgba(148,163,184,0.18), rgba(15,23,42,0.08))";
          return (
            <Link key={category.id} href={`/categories/${category.slug}`} className="glass glass-hover group overflow-hidden rounded-xl2">
              <div className="photo-frame relative aspect-[4/3]" style={{ background }}>
                <div className="absolute inset-0 bg-gradient-to-t from-base-950/50 via-transparent to-transparent" />
                <span className="absolute left-3 top-3 rounded-full border border-white/15 bg-base-950/50 px-2 py-1 text-[10px] font-medium text-ink-100 backdrop-blur">Explore</span>
              </div>
              <div className="flex items-center justify-between p-4">
                <div>
                  <p className="text-sm font-medium text-ink-100">{category.name}</p>
                  <p className="mt-1 truncate text-[11px] text-ink-500">{CATEGORY_DESCRIPTIONS[category.name] || "Explore curated products"}</p>
                  <p className="mt-2 text-[11px] font-medium text-astra-cyan">{category.product_count} listings</p>
                </div>
                <ArrowRight className="h-4 w-4 text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-astra-cyan" />
              </div>
            </Link>
          );
        })}
      </div>}
    </div>
  );
}

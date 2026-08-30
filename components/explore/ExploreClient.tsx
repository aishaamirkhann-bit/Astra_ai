"use client";

import { useEffect, useState } from "react";
import CategoryChips from "@/components/explore/CategoryChips";
import SemanticFilters from "@/components/explore/SemanticFilters";
import HybridResultsGrid, { type ExploreProduct } from "@/components/explore/HybridResultsGrid";
import SmartPrompt from "@/components/explore/SmartPrompt";
import { ImageIcon, Mic, RefreshCw, RotateCcw, X } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ExploreClient({
  initialQuery,
  initialCategory,
  initialWalletBalance,
}: {
  initialQuery: string;
  initialCategory: string | null;
  initialWalletBalance?: number | null;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [category, setCategory] = useState<string | null>(initialCategory);
  const [maxPrice, setMaxPrice] = useState(500000);
  const [minPrice, setMinPrice] = useState(0);
  const [semanticTags, setSemanticTags] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState("most_relevant");
  const [products, setProducts] = useState<ExploreProduct[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [budgetMode, setBudgetMode] = useState(false);
  const [walletBalance, setWalletBalance] = useState<number | null>(initialWalletBalance ?? null);
  const [retryKey, setRetryKey] = useState(0);
  const [searchContext, setSearchContext] = useState<{ mode: "voice" | "image"; label: string; previewUrl?: string } | null>(null);

  useEffect(() => {
    const loadWalletBalance = async () => {
      try {
        const response = await fetch(`${API_URL}/api/v1/explore/wallet`, { credentials: "include" });
        if (!response.ok) return;

        const payload = (await response.json()) as { available_balance?: unknown };
        if (typeof payload.available_balance === "number" && Number.isFinite(payload.available_balance)) {
          setWalletBalance(payload.available_balance);
        }
      } catch {
        // The explore catalog remains usable when the wallet service is unavailable.
      }
    };

    void loadWalletBalance();
  }, []);

  const resetExplore = () => {
    setBudgetMode(false);
    setQuery("");
    setCategory(null);
    setMinPrice(0);
    setMaxPrice(500000);
    setSemanticTags([]);
    setSortBy("most_relevant");
  };

  const checkBudget = async () => {
    setBudgetMode(true);
    setLoading(true);
    const body = new FormData();
    body.append("text_query", query);
    body.append("category", category || "All");
    body.append("min_price", String(minPrice));
    body.append("max_price", String(maxPrice));
    try {
      const response = await fetch(`${API_URL}/api/v1/explore/budget-recommendations`, { method: "POST", body, credentials: "include" });
      if (!response.ok) throw new Error("Budget service unavailable");
      const payload = await response.json();
      setProducts(payload.items);
      setTotalResults(payload.total_results);
      setError(null);
    } catch {
      setError("Could not calculate budget recommendations.");
    } finally {
      setLoading(false);
    }
  };

  const searchWithFile = async (file: File, queryType: "voice" | "image") => {
    setLoading(true);
    setError(null);
    const body = new FormData();
    body.append("query_type", queryType);
    body.append(queryType === "voice" ? "audio_file" : "image_file", file);
    body.append("category", category || "All");
    body.append("min_price", String(minPrice));
    body.append("max_price", String(maxPrice));
    body.append("sort_by", sortBy);
    body.append("limit", "50");
    semanticTags.forEach((tag) => body.append("semantic_tags", tag));
    try {
      const response = await fetch(`${API_URL}/api/v1/explore/search`, { method: "POST", body, credentials: "include" });
      if (!response.ok) throw new Error("Search service is unavailable");
      const payload = await response.json();
      const items = Array.isArray(payload) ? payload : payload.items;
      if (payload.query) window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: payload.query } }));
      setProducts(items);
      setTotalResults(Array.isArray(payload) ? payload.length : payload.total_results);
    } catch {
      setError("Could not process this file. Check that the Astra backend is running.");
      setProducts([]);
      setTotalResults(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const raw = window.sessionStorage.getItem("astra:image-search");
    if (!raw) return;
    window.sessionStorage.removeItem("astra:image-search");
    try {
      const saved = JSON.parse(raw) as { name: string; type: string; data: string };
      fetch(saved.data).then((response) => response.blob()).then((blob) => {
        const file = new File([blob], saved.name, { type: saved.type || blob.type });
        setSearchContext({ mode: "image", label: saved.name, previewUrl: URL.createObjectURL(blob) });
        void searchWithFile(file, "image");
      }).catch(() => setError("Could not restore the selected image search."));
    } catch { setError("Could not restore the selected image search."); }
    // This one-shot handoff intentionally runs only when Explore mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (budgetMode) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      const body = new FormData();
      body.append("query_type", "text");
      body.append("text_query", query);
      body.append("category", category || "All");
      body.append("min_price", String(minPrice));
      body.append("max_price", String(maxPrice));
      body.append("sort_by", sortBy);
      body.append("page", "1");
      body.append("limit", "50");
      semanticTags.forEach((tag) => body.append("semantic_tags", tag));

      try {
        const isDefaultCatalogRequest = !query.trim() && !category && minPrice === 0 && maxPrice === 500000 && semanticTags.length === 0 && sortBy === "most_relevant";
        const response = await fetch(
          isDefaultCatalogRequest ? `${API_URL}/api/v1/explore/products` : `${API_URL}/api/v1/explore/search`,
          isDefaultCatalogRequest ? { signal: controller.signal, credentials: "include" } : { method: "POST", body, signal: controller.signal, credentials: "include" },
        );
        if (!response.ok) throw new Error("Search service is unavailable");
        const payload = await response.json();
        const items = Array.isArray(payload) ? payload : payload.items;
        setProducts(items);
        setTotalResults(Array.isArray(payload) ? payload.length : payload.total_results);
        setError(null);
      } catch (requestError) {
        if (!controller.signal.aborted && (requestError as Error).name !== "AbortError") {
          setError("Could not connect to Astra search. Start the backend on port 8000.");
          setProducts([]);
          setTotalResults(0);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [category, maxPrice, minPrice, query, semanticTags, sortBy, budgetMode, retryKey]);

  useEffect(() => {
    const handleSearch = (event: Event) => {
      setQuery((event as CustomEvent<{ query: string }>).detail.query);
    };
    const handleFileSearch = (event: Event) => {
      const detail = (event as CustomEvent<{ file: File; queryType: "voice" | "image" }>).detail;
      void searchWithFile(detail.file, detail.queryType);
    };
    const handleSearchContext = (event: Event) => setSearchContext((event as CustomEvent<{ mode: "voice" | "image"; label: string; previewUrl?: string }>).detail);
    window.addEventListener("astra:search", handleSearch);
    window.addEventListener("astra:file-search", handleFileSearch);
    window.addEventListener("astra:search-context", handleSearchContext);
    return () => {
      window.removeEventListener("astra:search", handleSearch);
      window.removeEventListener("astra:file-search", handleFileSearch);
      window.removeEventListener("astra:search-context", handleSearchContext);
    };
  }, [category, minPrice, maxPrice, sortBy, semanticTags]);

  return (
    <>
      <SmartPrompt onSelect={(prompt) => { setBudgetMode(false); window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: prompt, commit: true } })); }} onBudgetCheck={() => void checkBudget()} />
      {typeof walletBalance === "number" && <p className="-mt-4 text-xs text-ink-500">Available Balance: <span className="font-semibold text-ink-100">Rs. {walletBalance.toLocaleString()}</span></p>}
      {searchContext && <div className="glass flex items-center gap-3 rounded-xl2 p-3"><div className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-lg bg-base-800">{searchContext.mode === "image" && searchContext.previewUrl ? <img src={searchContext.previewUrl} alt="Selected search" className="h-full w-full object-cover" /> : <Mic className="h-5 w-5 text-astra-cyan" />}</div><div className="min-w-0 flex-1"><p className="flex items-center gap-1.5 text-xs font-semibold text-ink-100">{searchContext.mode === "image" ? <ImageIcon className="h-3.5 w-3.5 text-astra-cyan" /> : <Mic className="h-3.5 w-3.5 text-astra-cyan" />}{searchContext.mode === "image" ? "Image search" : "Voice search"}</p><p className="mt-0.5 truncate text-[11px] text-ink-500">{searchContext.label}</p></div><button type="button" onClick={() => setSearchContext(null)} aria-label="Dismiss search context" className="text-ink-500 transition hover:text-ink-100"><X className="h-4 w-4" /></button></div>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <CategoryChips selected={category} onSelect={(value) => { setBudgetMode(false); setCategory(value); }} />
        {(query || category || minPrice !== 0 || maxPrice !== 500000 || semanticTags.length > 0 || sortBy !== "most_relevant") && <button type="button" onClick={resetExplore} className="inline-flex items-center gap-1.5 text-xs font-medium text-astra-cyan transition hover:text-ink-100"><RotateCcw className="h-3.5 w-3.5" /> Reset all</button>}
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <SemanticFilters
          maxPrice={maxPrice}
          onMaxPriceChange={(value) => { setBudgetMode(false); setMaxPrice(value); }}
          minPrice={minPrice}
          onMinPriceChange={(value) => { setBudgetMode(false); setMinPrice(value); }}
          activeTags={semanticTags}
          onTagsChange={(value) => { setBudgetMode(false); setSemanticTags(value); }}
        />
        <div>
          {error && <div className="mb-3 flex flex-col gap-3 rounded-xl border border-signal-reject/30 bg-signal-reject/10 p-4 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs text-signal-reject">{error}</p><button type="button" onClick={() => { if (budgetMode) void checkBudget(); else setRetryKey((value) => value + 1); }} className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-signal-reject/30 px-3 py-1.5 text-xs font-medium text-signal-reject transition hover:bg-signal-reject/10"><RefreshCw className="h-3.5 w-3.5" /> Retry</button></div>}
          <HybridResultsGrid products={products} totalResults={totalResults} sortBy={sortBy} onSortChange={(value) => { setBudgetMode(false); setSortBy(value); }} loading={loading} />
        </div>
      </div>
    </>
  );
}

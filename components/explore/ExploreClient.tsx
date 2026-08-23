"use client";

import { useEffect, useState } from "react";
import CategoryChips from "@/components/explore/CategoryChips";
import SemanticFilters from "@/components/explore/SemanticFilters";
import HybridResultsGrid, { type ExploreProduct } from "@/components/explore/HybridResultsGrid";
import SmartPrompt from "@/components/explore/SmartPrompt";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ExploreClient({
  initialQuery,
  initialCategory,
}: {
  initialQuery: string;
  initialCategory: string | null;
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
  const [walletBalance, setWalletBalance] = useState<number | null>(null);

  useEffect(() => {
    void fetch(`${API_URL}/api/v1/explore/wallet`).then((response) => response.json()).then((payload) => setWalletBalance(payload.available_balance));
  }, []);

  const checkBudget = async () => {
    setBudgetMode(true);
    setLoading(true);
    const body = new FormData();
    body.append("text_query", query);
    body.append("category", category || "All");
    body.append("min_price", String(minPrice));
    body.append("max_price", String(maxPrice));
    try {
      const response = await fetch(`${API_URL}/api/v1/explore/budget-recommendations`, { method: "POST", body });
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
    body.append("max_price", String(maxPrice));
    body.append("sort_by", sortBy);
    body.append("limit", "50");
    semanticTags.forEach((tag) => body.append("semantic_tags", tag));
    try {
      const response = await fetch(`${API_URL}/api/v1/explore/search`, { method: "POST", body });
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
    if (budgetMode) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      const body = new FormData();
      body.append("query_type", "text");
      body.append("text_query", query);
      body.append("category", category || "All");
      body.append("min_price", "0");
      body.append("max_price", String(maxPrice));
      body.append("sort_by", sortBy);
      body.append("page", "1");
      body.append("limit", "50");
      semanticTags.forEach((tag) => body.append("semantic_tags", tag));

      try {
        const isDefaultCatalogRequest = !query.trim() && !category && maxPrice === 500000 && semanticTags.length === 0 && sortBy === "most_relevant";
        const response = await fetch(
          isDefaultCatalogRequest ? `${API_URL}/api/v1/explore/products` : `${API_URL}/api/v1/explore/search`,
          isDefaultCatalogRequest ? { signal: controller.signal } : { method: "POST", body, signal: controller.signal },
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
  }, [category, maxPrice, minPrice, query, semanticTags, sortBy, budgetMode]);

  useEffect(() => {
    const handleSearch = (event: Event) => {
      setQuery((event as CustomEvent<{ query: string }>).detail.query);
    };
    const handleFileSearch = (event: Event) => {
      const detail = (event as CustomEvent<{ file: File; queryType: "voice" | "image" }>).detail;
      void searchWithFile(detail.file, detail.queryType);
    };
    window.addEventListener("astra:search", handleSearch);
    window.addEventListener("astra:file-search", handleFileSearch);
    return () => {
      window.removeEventListener("astra:search", handleSearch);
      window.removeEventListener("astra:file-search", handleFileSearch);
    };
  }, []);

  return (
    <>
      <SmartPrompt onSelect={(prompt) => { setBudgetMode(false); window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: prompt, commit: true } })); }} onBudgetCheck={() => void checkBudget()} />
      {walletBalance !== null && <p className="-mt-4 text-xs text-ink-500">Available Balance: <span className="font-semibold text-ink-100">Rs. {walletBalance.toLocaleString()}</span></p>}

      <CategoryChips selected={category} onSelect={setCategory} />

      <div className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <SemanticFilters
          maxPrice={maxPrice}
          onMaxPriceChange={setMaxPrice}
          minPrice={minPrice}
          onMinPriceChange={setMinPrice}
          activeTags={semanticTags}
          onTagsChange={setSemanticTags}
        />
        <div>
          {error && <p className="mb-3 rounded-lg border border-signal-reject/30 bg-signal-reject/10 p-3 text-xs text-signal-reject">{error}</p>}
          {loading ? <p className="text-sm text-ink-500">Searching Astra...</p> : <HybridResultsGrid products={products} totalResults={totalResults} sortBy={sortBy} onSortChange={setSortBy} />}
        </div>
      </div>
    </>
  );
}

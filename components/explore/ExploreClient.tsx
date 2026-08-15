"use client";

import { useMemo, useState } from "react";
import MultiModalSearch from "@/components/explore/MultiModalSearch";
import CategoryChips from "@/components/explore/CategoryChips";
import SemanticFilters from "@/components/explore/SemanticFilters";
import HybridResultsGrid from "@/components/explore/HybridResultsGrid";
import { PRODUCTS } from "@/lib/mockData";

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

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return PRODUCTS.filter((p) => {
      const priceNum = Number(p.price.replace(/[^0-9]/g, ""));
      const matchesCategory = !category || p.category === category;
      const matchesQuery = !q || p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q);
      const matchesPrice = priceNum <= maxPrice;
      return matchesCategory && matchesQuery && matchesPrice;
    });
  }, [query, category, maxPrice]);

  return (
    <>
      <MultiModalSearch query={query} onQueryChange={setQuery} />

      <CategoryChips selected={category} onSelect={setCategory} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
        <SemanticFilters maxPrice={maxPrice} onMaxPriceChange={setMaxPrice} />
        <HybridResultsGrid products={results} />
      </div>
    </>
  );
}

"use client";

import { SlidersHorizontal } from "lucide-react";

const DEFAULT_SEMANTIC_TAGS = [
  "Verified seller",
  "Bestseller",
  "Fast delivery",
  "Eco-friendly",
  "Highly rated",
];

export default function SemanticFilters({
  minPrice,
  onMinPriceChange,
  maxPrice,
  onMaxPriceChange,
  activeTags,
  onTagsChange,
  tags,
}: {
  minPrice: number;
  onMinPriceChange: (v: number) => void;
  maxPrice: number;
  onMaxPriceChange: (v: number) => void;
  activeTags: string[];
  onTagsChange: (tags: string[]) => void;
  tags?: string[];
}) {
  const toggle = (tag: string) =>
    onTagsChange(activeTags.includes(tag) ? activeTags.filter((t) => t !== tag) : [...activeTags, tag]);

  const chipList = tags && tags.length > 0 ? tags : DEFAULT_SEMANTIC_TAGS;

  return (
    <aside className="glass h-fit rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">Refine results</h2>
      </div>

      <div className="mb-6">
        <p className="mb-2 text-xs font-medium text-ink-300">Semantic tags</p>
        <div className="flex flex-wrap gap-2">
          {chipList.map((tag) => {
            const on = activeTags.includes(tag);
            return (
              <button
                key={tag}
                onClick={() => toggle(tag)}
                className={[
                  "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                  on
                    ? "border-astra-violet/50 bg-astra-gradient-soft text-ink-100"
                    : "border-base-600 text-ink-500 hover:text-ink-300",
                ].join(" ")}
              >
                {tag}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-medium text-ink-300">Min price</p>
          <p className="font-mono text-[11px] text-astra-cyan">Rs. {minPrice.toLocaleString()}</p>
        </div>
        <input type="range" min={0} max={500000} step={5000} value={minPrice} onChange={(e) => onMinPriceChange(Math.min(Number(e.target.value), maxPrice))} className="mb-3 w-full accent-astra-cyan" />
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-medium text-ink-300">Max price</p>
          <p className="font-mono text-[11px] text-astra-cyan">Rs. {maxPrice.toLocaleString()}</p>
        </div>
        <input
          type="range"
          min={5000}
          max={500000}
          step={5000}
          value={maxPrice}
          onChange={(e) => onMaxPriceChange(Number(e.target.value))}
          className="w-full accent-astra-violet"
        />
        <div className="mt-1 flex justify-between text-[10px] text-ink-700">
          <span>Rs. 5k</span>
          <span>Rs. 500k</span>
        </div>
      </div>
    </aside>
  );
}

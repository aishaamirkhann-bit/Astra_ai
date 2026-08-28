"use client";

import { EXPLORE_CATEGORY_TAGS } from "@/lib/mockData";

export default function CategoryChips({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (c: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onSelect(null)}
        className={[
          "rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors",
          selected === null
            ? "bg-astra-gradient text-white shadow-glow"
            : "border border-base-600 text-ink-300 hover:text-ink-100",
        ].join(" ")}
      >
        All
      </button>
      {EXPLORE_CATEGORY_TAGS.map((c) => (
        <button
          key={c}
          onClick={() => onSelect(c)}
          className={[
            "rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors",
            selected === c
              ? "bg-astra-gradient text-white shadow-glow"
              : "border border-base-600 text-ink-300 hover:text-ink-100",
          ].join(" ")}
        >
          {c}
        </button>
      ))}
    </div>
  );
}

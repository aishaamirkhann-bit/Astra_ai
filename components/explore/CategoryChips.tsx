"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CategoryChips({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (c: string | null) => void;
}) {
  const [categories, setCategories] = useState<string[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/v1/explore/categories`, { signal: controller.signal, credentials: "include" })
      .then((response) => {
        if (!response.ok) throw new Error("Categories unavailable");
        return response.json() as Promise<Array<{ name: string }>>;
      })
      .then((items) => setCategories(items.map((item) => item.name)))
      .catch(() => setCategories([]));

    return () => controller.abort();
  }, []);

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
      {categories.map((c) => (
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

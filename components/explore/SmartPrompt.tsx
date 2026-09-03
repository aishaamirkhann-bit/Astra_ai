"use client";

import { Sparkles } from "lucide-react";

const PROMPTS = [
  { label: "Laptop under 200k", query: "gaming laptop 200k ke under" },
  { label: "Sober formal shoes", query: "sober formal shoes" },
  { label: "Noise Cancelling Headphones", query: "noise cancelling headphones" },
  { label: "Mera budget check karo", query: "Mera budget check karo" },
];

export default function SmartPrompt({ onSelect, onBudgetCheck }: { onSelect: (query: string) => void; onBudgetCheck: () => void }) {
  return (
    <section className="glass rounded-xl2 p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-astra-cyan" />
        <div>
          <p className="font-display text-sm font-semibold text-ink-100">AI smart prompts</p>
          <p className="text-[11px] text-ink-500">Start with a buying idea</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt.query}
            type="button"
            onClick={() => prompt.label === "Mera budget check karo" ? onBudgetCheck() : onSelect(prompt.query)}
            className="rounded-full border border-base-600 bg-base-800/60 px-3 py-2 text-left text-[11px] font-medium text-ink-300 transition-colors hover:border-astra-cyan/60 hover:text-ink-100"
          >
            {prompt.label}
          </button>
        ))}
      </div>
    </section>
  );
}

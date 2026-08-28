"use client";

import { useState } from "react";
import { Search, Mic, ImagePlus, UploadCloud } from "lucide-react";

const MODES = [
  { id: "text", label: "Text", icon: Search },
  { id: "voice", label: "Voice", icon: Mic },
  { id: "image", label: "Image", icon: ImagePlus },
] as const;

type Mode = (typeof MODES)[number]["id"];

export default function MultiModalSearch({
  query,
  onQueryChange,
}: {
  query: string;
  onQueryChange: (q: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("text");
  const [listening, setListening] = useState(false);

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 inline-flex rounded-lg bg-base-800 p-1">
        {MODES.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            className={[
              "flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors",
              mode === id
                ? "bg-astra-gradient text-white shadow-glow"
                : "text-ink-500 hover:text-ink-100",
            ].join(" ")}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {mode === "text" && (
        <div className="flex items-center gap-3 rounded-xl border border-base-600 bg-base-800/60 px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-ink-500" />
          <input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder='Try "gaming laptop 200k ke under" or "sober formal shoes"'
            className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-700 focus:outline-none"
          />
          {query && (
            <button
              onClick={() => onQueryChange("")}
              className="shrink-0 text-[11px] text-ink-500 hover:text-ink-100"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {mode === "voice" && (
        <button
          onClick={() => setListening((v) => !v)}
          className="flex w-full items-center justify-center gap-4 rounded-xl border border-base-600 bg-base-800/60 px-4 py-6 transition-colors hover:border-astra-violet/40"
        >
          <div className="flex h-8 items-end gap-1">
            {[6, 14, 22, 12, 18, 8].map((h, i) => (
              <span
                key={i}
                style={{
                  height: listening ? `${h}px` : "4px",
                  transitionDelay: `${i * 40}ms`,
                }}
                className="w-1 rounded-full bg-astra-cyan opacity-30 transition-all duration-300 [&[style*='opacity:1']]:opacity-100"
              />
            ))}
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-ink-100">
              {listening ? "Sun raha hoon, boliye…" : "Tap and speak your search"}
            </p>
            <p className="text-[11px] text-ink-500">English · Urdu · Roman Urdu supported</p>
          </div>
        </button>
      )}

      {mode === "image" && (
        <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-base-500 bg-base-800/40 px-4 py-8 text-center transition-colors hover:border-astra-violet/50">
          <UploadCloud className="h-6 w-6 text-astra-cyan" />
          <p className="text-sm font-medium text-ink-100">Drop an image or tap to upload</p>
          <p className="text-[11px] text-ink-500">
            ASTRA finds visually and semantically similar listings
          </p>
          <input type="file" accept="image/*" className="hidden" />
        </label>
      )}
    </section>
  );
}

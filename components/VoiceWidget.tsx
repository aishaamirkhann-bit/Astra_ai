"use client";

import { useState } from "react";
import Link from "next/link";
import { Mic } from "lucide-react";

const BAR_HEIGHTS = [6, 14, 22, 12, 26, 10, 18, 8, 20, 14, 6];

export default function VoiceWidget() {
  const [listening, setListening] = useState(false);

  return (
    <section className="glass glass-hover rounded-xl2 p-5 text-center">
      <h2 className="mb-4 font-display text-sm font-semibold text-ink-100">ASTRA Voice</h2>

      <button
        onClick={() => setListening((v) => !v)}
        aria-pressed={listening}
        className={[
          "mx-auto grid h-16 w-16 place-items-center rounded-full transition-all",
          listening ? "bg-astra-gradient shadow-glow" : "bg-base-800 hover:bg-base-700",
        ].join(" ")}
      >
        <Mic className={["h-6 w-6", listening ? "text-white" : "text-ink-300"].join(" ")} />
      </button>

      <div className="mt-4 flex h-8 items-end justify-center gap-1" aria-hidden="true">
        {BAR_HEIGHTS.map((h, i) => (
          <span
            key={i}
            className={[
              "w-1 rounded-full bg-astra-gradient transition-all duration-300",
              listening ? "opacity-100" : "opacity-30",
            ].join(" ")}
            style={{
              height: listening ? `${h}px` : "4px",
              transitionDelay: `${i * 40}ms`,
            }}
          />
        ))}
      </div>

      <p className="mt-3 text-xs text-ink-300">
        {listening ? "Sun rahe hain…" : "Bolo, ASTRA suney ga"}
      </p>

      <Link
        href="/messages"
        className="mt-4 inline-block rounded-lg bg-astra-gradient px-4 py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90"
      >
        Try Now
      </Link>
    </section>
  );
}

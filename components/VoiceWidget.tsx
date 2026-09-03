"use client";

import { useState } from "react";
import Link from "next/link";
import { Mic } from "lucide-react";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";

const BAR_HEIGHTS = [6, 14, 22, 12, 26, 10, 18, 8, 20, 14, 6];

export default function VoiceWidget() {
  const [lastTranscript, setLastTranscript] = useState("");

  const { listening, interim, start, stop } = useSpeechRecognition({
    onFinal: (text) => {
      setLastTranscript(text);
      window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: text, commit: true } }));
    },
  });

  return (
    <section className="glass glass-hover rounded-xl2 p-5 text-center">
      <h2 className="mb-4 font-display text-sm font-semibold text-ink-100">ASTRA Voice</h2>

      <button
        onClick={() => (listening ? stop() : start())}
        aria-pressed={listening}
        aria-label={listening ? "Stop listening" : "Start listening"}
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

      <p className="mt-3 min-h-4 text-xs text-ink-300">
        {listening ? interim || "Sun rahe hain…" : lastTranscript || "Bolo, ASTRA suney ga"}
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

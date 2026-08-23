"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Mic, X, ArrowUpRight } from "lucide-react";

const BAR_HEIGHTS = [6, 16, 24, 12, 20, 8];

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export default function GlobalVoiceFab() {
  const [open, setOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const toggleListening = () => {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }
    const speechWindow = window as Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const SpeechRecognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setTranscript("Use Chrome or Edge for voice search");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const value = event.results[0][0].transcript;
      setTranscript(value);
      window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: value, commit: true } }));
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onerror = () => {
      setListening(false);
      recognitionRef.current = null;
      setTranscript("Voice search could not hear that");
    };
    recognitionRef.current = recognition;
    setTranscript("");
    setListening(true);
    try {
      recognition.start();
    } catch {
      setListening(false);
      recognitionRef.current = null;
      setTranscript("Microphone permission required. Allow and try again.");
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
      {open && (
        <div className="glass w-64 rounded-xl2 p-4 shadow-glow">
          <div className="mb-3 flex items-center justify-between">
            <p className="font-display text-xs font-semibold text-ink-100">ASTRA Voice</p>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close voice assistant"
              className="text-ink-500 hover:text-ink-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <button
            onClick={toggleListening}
            aria-pressed={listening}
            aria-label={listening ? "Stop voice search" : "Start voice search"}
            className={[
              "mx-auto grid h-12 w-12 place-items-center rounded-full transition-all",
              listening ? "bg-astra-gradient shadow-glow" : "bg-base-800 hover:bg-base-700",
            ].join(" ")}
          >
            <Mic className={["h-5 w-5", listening ? "text-white" : "text-ink-300"].join(" ")} />
          </button>

          <div className="mt-3 flex h-6 items-end justify-center gap-1" aria-hidden="true">
            {BAR_HEIGHTS.map((h, i) => (
              <span
                key={i}
                className="w-1 rounded-full bg-astra-gradient transition-all duration-300"
                style={{ height: listening ? `${h}px` : "3px", opacity: listening ? 1 : 0.3 }}
              />
            ))}
          </div>

          <p className="mt-2 text-center text-[11px] text-ink-300">
            {listening ? "Sun rahe hain..." : transcript || "Bolo, ASTRA suney ga"}
          </p>

          <Link
            href="/messages"
            className="mt-3 flex items-center justify-center gap-1 text-[11px] font-medium text-ink-500 hover:text-ink-100"
          >
            Open full voice history <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Open ASTRA voice assistant"
        aria-expanded={open}
        className="grid h-14 w-14 place-items-center rounded-full bg-astra-gradient text-white shadow-glow transition-transform hover:scale-105"
      >
        {open ? <X className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
      </button>
    </div>
  );
}

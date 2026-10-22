"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Mic, X, ArrowUpRight } from "lucide-react";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import { isARIntent } from "@/lib/arIntent";
import { getVoiceWebSocketUrl } from "@/lib/api";
import { flushVoiceEvents, interruptVoiceOutput, parseVoiceEvent, sendVoiceTranscript } from "@/lib/voiceStream.mjs";

const BAR_HEIGHTS = [6, 16, 24, 12, 20, 8];

export default function GlobalVoiceFab() {
  const [open, setOpen] = useState(false);
  const [lastTranscript, setLastTranscript] = useState("");
  const [streamStatus, setStreamStatus] = useState("ready");
  const voiceSocket = useRef<WebSocket | null>(null);
  const pendingEvents = useRef<string[]>([]);

  useEffect(() => {
    if (!open) return;
    const socket = new WebSocket(getVoiceWebSocketUrl());
    voiceSocket.current = socket;
    socket.onopen = () => flushVoiceEvents(socket, pendingEvents.current);
    socket.onmessage = (message) => {
      const event = parseVoiceEvent(message.data) as { type?: string; final?: boolean } | null;
      if (event?.type === "transcript" && event.final) setStreamStatus("ready");
      if (event?.type === "interrupted") setStreamStatus("interrupted");
    };
    socket.onclose = () => { if (voiceSocket.current === socket) voiceSocket.current = null; };
    return () => { socket.close(); if (voiceSocket.current === socket) voiceSocket.current = null; };
  }, [open]);

  const { listening, interim, start, stop } = useSpeechRecognition({
    onFinal: (text) => {
      setLastTranscript(text);
      setStreamStatus("processing");
      sendVoiceTranscript(voiceSocket.current, pendingEvents.current, text, true);
      if (isARIntent(text)) {
        if (window.location.pathname.startsWith("/product/")) {
          window.dispatchEvent(new CustomEvent("astra:ar-intent"));
        } else {
          setLastTranscript("Open a product page to preview it in AR");
        }
        return;
      }
      window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: text, commit: true } }));
    },
  });

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
            onClick={() => {
              if (listening) stop();
              else { interruptVoiceOutput(voiceSocket.current, window.speechSynthesis); start(); }
            }}
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

          <p className="mt-2 min-h-8 text-center text-[11px] text-ink-300">
            {listening ? interim || "Sun rahe hain..." : streamStatus === "processing" ? "Processing..." : streamStatus === "interrupted" ? "Interrupted" : lastTranscript || "Bolo, ASTRA suney ga"}
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

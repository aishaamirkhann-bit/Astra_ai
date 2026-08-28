"use client";

import { useState } from "react";
import { Mic, Send, ShieldHalf } from "lucide-react";
import PageShell from "@/components/PageShell";
import { VOICE_HISTORY } from "@/lib/mockData";

export default function MessagesPage() {
  const [draft, setDraft] = useState("");

  return (
    <PageShell
      active="Messages"
      title="Messages"
      subtitle="Your ASTRA Voice Copilot history — every conversation, in English or Roman Urdu."
    >
      <div className="glass flex flex-col rounded-xl2 p-5">
        <div className="scroll-thin flex max-h-[520px] flex-col gap-5 overflow-y-auto pr-1">
          {VOICE_HISTORY.map((c) => (
            <div key={c.id} className="flex flex-col gap-3">
              <p className="text-center text-[10px] uppercase tracking-wide text-ink-700">
                {c.time}
              </p>

              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-astra-gradient px-4 py-2.5 text-sm text-white">
                  {c.you}
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
                  <ShieldHalf className="h-3.5 w-3.5 text-astra-cyan" />
                </div>
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100">
                  {c.astra}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 flex items-center gap-2 border-t border-base-600 pt-4">
          <button
            aria-label="Speak to ASTRA"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-base-800 text-ink-300 hover:text-ink-100"
          >
            <Mic className="h-4 w-4" />
          </button>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message to ASTRA…"
            className="flex-1 rounded-full border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100 placeholder:text-ink-700 focus:outline-none"
          />
          <button
            aria-label="Send message"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-astra-gradient text-white hover:opacity-90"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </PageShell>
  );
}

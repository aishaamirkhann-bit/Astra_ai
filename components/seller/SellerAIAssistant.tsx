"use client";

import { FormEvent, useRef, useState } from "react";
import { Bot, Loader2, Send, Sparkles } from "lucide-react";
import { askSellerAssistant, sendMultimodalChat } from "@/lib/api";

type Message = { role: "assistant" | "seller"; text: string };
const suggestions = ["How is my inventory doing?", "Any COD orders needing review?", "Explain my bundle price floors", "What should I do with pending orders?"];

export default function SellerAIAssistant() {
  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", text: "Hi! I can summarize your inventory, advisory COD signals, bundle price floors, and order statuses." }]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pastedImage, setPastedImage] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function send(event?: FormEvent, text = query) {
    event?.preventDefault();
    const trimmed = text.trim();
    if ((!trimmed && !pastedImage) || busy) return;
    const image = pastedImage;
    setError("");
    setQuery("");
    setPastedImage(null);
    inputRef.current?.focus({ preventScroll: true });
    setMessages((current) => [...current, { role: "seller", text: trimmed || "Product image attached" }]);
    setBusy(true);
    try {
      const answer = image
        ? await sendMultimodalChat({ message: trimmed, image })
        : await askSellerAssistant(trimmed);
      setMessages((current) => [...current, { role: "assistant", text: "message" in answer ? answer.message : answer.reply_text }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Assistant is unavailable right now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="seller-assistant-title" className="rounded-2xl border border-violet-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2"><span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-100 text-violet-700"><Bot className="h-4 w-4" /></span><div><h3 id="seller-assistant-title" className="font-display text-sm font-bold text-slate-900">Astra Seller Assistant</h3><p className="mt-0.5 text-[11px] text-slate-500">Ask about your seller workspace</p></div></div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[9px] font-semibold text-emerald-700">Read only</span>
      </div>
      <div aria-live="polite" className="mt-4 max-h-64 space-y-2 overflow-y-auto rounded-xl bg-slate-50 p-3">
        {messages.map((message, index) => <p key={`${index}-${message.role}`} className={`max-w-[90%] whitespace-pre-wrap rounded-xl px-3 py-2 text-xs leading-relaxed ${message.role === "seller" ? "ml-auto bg-violet-600 text-white" : "border border-slate-200 bg-white text-slate-700"}`}>{message.text}</p>)}
        {busy && <p className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Reviewing your seller data…</p>}
      </div>
      {error && <p role="alert" className="mt-2 text-xs text-rose-700">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">{suggestions.map((suggestion) => <button key={suggestion} type="button" disabled={busy} onClick={() => void send(undefined, suggestion)} className="inline-flex items-center gap-1 rounded-full border border-violet-200 px-2.5 py-1.5 text-[10px] font-medium text-violet-800 hover:bg-violet-50 disabled:opacity-50"><Sparkles className="h-3 w-3" />{suggestion}</button>)}</div>
      <form onSubmit={(event) => void send(event)} className="mt-3 flex gap-2">
        <label className="sr-only" htmlFor="seller-ai-message">Message Astra Seller Assistant</label>
        <input ref={inputRef} id="seller-ai-message" inputMode="text" value={query} onChange={(event) => setQuery(event.target.value)} onPaste={(event) => { const image = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"))?.getAsFile(); if (image) { event.preventDefault(); if (["image/jpeg", "image/png", "image/webp"].includes(image.type) && image.size <= 8 * 1024 * 1024) { setPastedImage(image); setError(""); } else { setError("Paste a JPEG, PNG, or WebP image under 8 MB."); } } }} maxLength={500} placeholder="Ask about inventory, COD risk, prices…" className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-900 outline-none placeholder:text-slate-400 focus:border-violet-400" />
        <button type="submit" disabled={busy || (!query.trim() && !pastedImage)} aria-label="Send message" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-violet-700 text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-50"><Send className="h-4 w-4" /></button>
      </form>
      {pastedImage && <p className="mt-2 text-[10px] text-slate-600">Image ready: {pastedImage.name || "pasted image"} · paste text or a URL normally, or send this image for ASTRA Vision review.</p>}
    </section>
  );
}

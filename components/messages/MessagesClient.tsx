"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Mic, Plus, Send, ShieldHalf, Square } from "lucide-react";
import { getChatHistory, streamChat } from "@/lib/api";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import type { ChatConversation, ChatMessage } from "@/lib/types";

export default function MessagesClient() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { listening, interim, start: startVoice, stop: stopVoice } = useSpeechRecognition({
    onFinal: (text) => setDraft((current) => (current ? `${current} ${text}` : text)),
  });

  const active = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [conversations, activeId],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const history = await getChatHistory();
        if (cancelled) return;
        setConversations(history);
        setActiveId(history[0]?.id ?? null);
        setError(null);
      } catch (requestError) {
        if (!cancelled) setError((requestError as Error).message || "Could not load chat history.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [active?.messages.length, streamingText, pendingUserText]);

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    setPendingUserText(text);
    setStreamingText("");
    try {
      const response = await streamChat({ message: text, conversation_id: activeId ?? undefined });
      if (!response.ok || !response.body) {
        throw new Error(response.status === 401 ? "Session expired — please log in again." : `Chat request failed (${response.status})`);
      }
      let nextConversationId: number | null = null;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line) as { type: string; value?: string; conversation_id?: number };
            if (event.type === "meta" && typeof event.conversation_id === "number") {
              nextConversationId = event.conversation_id;
            } else if (event.type === "token" && event.value) {
              setStreamingText((current) => (current ?? "") + event.value);
            }
          } catch {
            // Ignore malformed stream lines.
          }
        }
      }
      try {
        const history = await getChatHistory();
        setConversations(history);
        setActiveId(nextConversationId ?? history[0]?.id ?? null);
      } catch {
        // The message is already persisted and streamed. Keep it visible even
        // when a background history refresh briefly loses the connection.
        const fallbackId = nextConversationId ?? activeId ?? -Date.now();
        const now = new Date().toISOString();
        const userMessage: ChatMessage = { id: `local-user-${now}`, role: "user", content: text, card_type: null, card: null, created_at: now };
        const assistantMessage: ChatMessage = { id: `local-assistant-${now}`, role: "assistant", content: streamingText ?? "", card_type: null, card: null, created_at: now };
        setConversations((current) => {
          const existing = current.find((conversation) => conversation.id === fallbackId);
          if (existing) {
            return current.map((conversation) => conversation.id === fallbackId
              ? { ...conversation, messages: [...conversation.messages, userMessage, assistantMessage] }
              : conversation);
          }
          return [...current, { id: fallbackId, title: text.slice(0, 70), messages: [userMessage, assistantMessage] }];
        });
        setActiveId(fallbackId);
        setError("Reply received. Conversation history will sync when the connection recovers.");
      }
    } catch (requestError) {
      setError((requestError as Error).message || "Could not reach the ASTRA chat service.");
    } finally {
      setSending(false);
      setStreamingText(null);
      setPendingUserText(null);
    }
  };

  const startNewConversation = () => {
    setActiveId(null);
    setDraft("");
  };

  const renderMessage = (message: ChatMessage, key: string | number) =>
    message.role === "user" ? (
      <div key={key} className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-astra-gradient px-4 py-2.5 text-sm text-white">
          {message.content}
        </div>
      </div>
    ) : (
      <div key={key} className="flex items-start gap-2">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
          <ShieldHalf className="h-3.5 w-3.5 text-astra-cyan" />
        </div>
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100">
          {message.content}
          {message.card && (
            <Link
              href={`/product/${message.card.slug}`}
              className="mt-3 flex items-center gap-3 rounded-xl border border-base-600 bg-base-900/70 p-2.5 transition hover:border-astra-indigo"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={message.card.image} alt={message.card.name} className="h-12 w-12 rounded-lg object-cover" />
              <span className="min-w-0">
                <span className="block truncate text-xs font-semibold text-ink-100">{message.card.name}</span>
                <span className="block text-[10px] text-ink-500">
                  Rs. {message.card.price.toLocaleString()} · {message.card.trust}% trust · {message.card.stock} in stock
                </span>
              </span>
            </Link>
          )}
        </div>
      </div>
    );

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside className="glass h-fit rounded-xl2 p-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">Conversations</p>
          <button
            type="button"
            onClick={startNewConversation}
            className="inline-flex items-center gap-1 rounded-lg border border-base-600 px-2 py-1 text-[10px] font-medium text-ink-300 transition hover:text-ink-100"
          >
            <Plus className="h-3 w-3" /> New
          </button>
        </div>
        {loading ? (
          <p className="text-xs text-ink-700">Loading history…</p>
        ) : conversations.length === 0 ? (
          <p className="text-xs text-ink-700">No conversations yet — ask ASTRA anything below.</p>
        ) : (
          <ul className="scroll-thin flex max-h-[420px] flex-col gap-1 overflow-y-auto">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => setActiveId(conversation.id)}
                  className={[
                    "w-full truncate rounded-lg px-3 py-2 text-left text-xs transition",
                    conversation.id === activeId
                      ? "bg-astra-gradient-soft text-ink-100"
                      : "text-ink-500 hover:bg-base-800 hover:text-ink-300",
                  ].join(" ")}
                >
                  {conversation.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="glass flex flex-col rounded-xl2 p-5">
        <div ref={scrollRef} className="scroll-thin flex max-h-[520px] min-h-[280px] flex-col gap-5 overflow-y-auto pr-1">
          {!loading && !active && !pendingUserText && (
            <p className="m-auto text-center text-xs text-ink-700">
              Start a conversation — try “laptop 150k ke under” or “what is my wallet balance?”
            </p>
          )}
          {(active?.messages ?? []).map((message) => renderMessage(message, message.id))}
          {pendingUserText && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-astra-gradient px-4 py-2.5 text-sm text-white opacity-80">
                {pendingUserText}
              </div>
            </div>
          )}
          {streamingText !== null && (
            <div className="flex items-start gap-2">
              <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
                <ShieldHalf className="h-3.5 w-3.5 text-astra-cyan" />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100">
                {streamingText || "…"}
              </div>
            </div>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-signal-reject">{error}</p>}

        <div className="mt-5 flex items-center gap-2 border-t border-base-600 pt-4">
          <button
            aria-label={listening ? "Stop dictation" : "Speak to ASTRA"}
            aria-pressed={listening}
            onClick={() => (listening ? stopVoice() : startVoice())}
            className={[
              "grid h-10 w-10 shrink-0 place-items-center rounded-full transition",
              listening ? "bg-astra-gradient text-white" : "bg-base-800 text-ink-300 hover:text-ink-100",
            ].join(" ")}
          >
            {listening ? <Square className="h-3.5 w-3.5" /> : <Mic className="h-4 w-4" />}
          </button>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder={listening ? interim || "Listening…" : "Type a message to ASTRA…"}
            className="flex-1 rounded-full border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100 placeholder:text-ink-700 focus:outline-none"
          />
          <button
            aria-label="Send message"
            onClick={() => void send()}
            disabled={sending || !draft.trim()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-astra-gradient text-white hover:opacity-90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

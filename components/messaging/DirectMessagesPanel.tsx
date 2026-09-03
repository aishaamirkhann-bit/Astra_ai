"use client";

import { useCallback, useEffect, useState } from "react";
import { Store, ChevronLeft, Users } from "lucide-react";
import ChatThread from "@/components/messaging/ChatThread";
import { getDirectConversations } from "@/lib/api";
import type { DirectConversation } from "@/lib/types";

/** Buyer/seller inbox of direct conversations with a live thread view. */
export default function DirectMessagesPanel() {
  const [conversations, setConversations] = useState<DirectConversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setConversations(await getDirectConversations());
      setError(null);
    } catch (requestError) {
      setError((requestError as Error).message || "Could not load direct messages.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const selected = conversations.find((conversation) => conversation.id === selectedId) ?? null;

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Users className="h-4 w-4 text-astra-cyan" />
        <h2 className="font-display text-sm font-semibold text-ink-100">Direct messages</h2>
        <span className="ml-auto text-[10px] text-ink-700">Buyer ↔ Seller · real-time</span>
      </div>

      {loading ? (
        <p className="py-6 text-center text-xs text-ink-700">Loading conversations…</p>
      ) : error ? (
        <p className="py-6 text-center text-xs text-signal-reject">{error}</p>
      ) : conversations.length === 0 ? (
        <p className="py-6 text-center text-xs text-ink-700">
          No direct conversations yet — buyers can reach you from any product page via “Message Seller”.
        </p>
      ) : selected ? (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              aria-label="Back to conversation list"
              className="rounded-lg border border-base-600 p-1.5 text-ink-500 hover:text-ink-100"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 truncate text-xs font-semibold text-ink-100">
                <Store className="h-3 w-3 text-astra-cyan" /> {selected.other_name}
              </p>
              {selected.product_title && <p className="truncate text-[10px] text-ink-500">About: {selected.product_title}</p>}
            </div>
          </div>
          <ChatThread conversationId={selected.id} />
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                onClick={() => setSelectedId(conversation.id)}
                className="flex w-full items-center gap-3 rounded-xl border border-base-600 bg-base-800/40 px-4 py-3 text-left transition hover:border-astra-violet/50"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
                  <Store className="h-4 w-4 text-astra-cyan" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-xs font-semibold text-ink-100">{conversation.other_name}</span>
                    {conversation.last_message_at && (
                      <span className="shrink-0 text-[9px] text-ink-700">
                        {new Date(conversation.last_message_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    )}
                  </span>
                  <span className="block truncate text-[11px] text-ink-500">
                    {conversation.product_title ? `${conversation.product_title} — ` : ""}
                    {conversation.last_message ?? "No messages yet"}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

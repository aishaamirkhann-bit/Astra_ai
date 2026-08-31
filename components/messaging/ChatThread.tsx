"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, Send, Square } from "lucide-react";
import { getDirectMessages, getCurrentUser, getMessagingWebSocketUrl, sendDirectMessage } from "@/lib/api";
import { showToast } from "@/lib/toast";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import type { DirectMessageOut } from "@/lib/types";

/** Live buyer<->seller thread: REST history + WebSocket fan-out. */
export default function ChatThread({
  conversationId,
  currentUserId,
}: {
  conversationId: number;
  currentUserId?: number;
}) {
  const [messages, setMessages] = useState<DirectMessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [userId, setUserId] = useState<number | null>(currentUserId ?? null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (userId !== null) return;
    getCurrentUser()
      .then((user) => setUserId(user.id))
      .catch(() => showToast("Could not resolve your session for messaging.", "error"));
  }, [userId]);

  const { listening, interim, start: startVoice, stop: stopVoice } = useSpeechRecognition({
    onFinal: (text) => setDraft((current) => (current ? `${current} ${text}` : text)),
  });

  useEffect(() => {
    if (userId === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDirectMessages(conversationId)
      .then((items) => {
        if (!cancelled) setMessages(items);
      })
      .catch((requestError: Error) => {
        if (!cancelled) setError(requestError.message || "Could not load messages.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const socket = new WebSocket(getMessagingWebSocketUrl(conversationId));
    socketRef.current = socket;
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type?: string; id?: number; content?: string; sender_id?: number; created_at?: string | null; conversation_id?: number };
        if (payload.type !== "message" || payload.conversation_id !== conversationId || typeof payload.id !== "number") return;
        const messageId = payload.id;
        setMessages((current) =>
          current.some((message) => message.id === messageId)
            ? current
            : [...current, {
                id: messageId,
                conversation_id: conversationId,
                sender_id: payload.sender_id ?? 0,
                sender_name: payload.sender_id === userId ? "You" : "Them",
                content: payload.content ?? "",
                created_at: payload.created_at ?? null,
              }],
        );
      } catch {
        // Ignore malformed socket frames.
      }
    };

    return () => {
      cancelled = true;
      socket.close();
      socketRef.current = null;
    };
  }, [conversationId, userId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length, interim]);

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    try {
      await sendDirectMessage(conversationId, text);
      // The WebSocket broadcast appends the persisted message; if the socket
      // dropped, fall back to reloading history.
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        setMessages(await getDirectMessages(conversationId));
      }
    } catch (requestError) {
      setError((requestError as Error).message || "Message could not be sent.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex min-h-[320px] flex-col">
      <div ref={scrollRef} className="scroll-thin flex max-h-[420px] min-h-[240px] flex-1 flex-col gap-3 overflow-y-auto pr-1">
        {loading ? (
          <p className="m-auto text-xs text-ink-700">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="m-auto text-center text-xs text-ink-700">No messages yet — say assalam o alaikum!</p>
        ) : (
          messages.map((message) => {
            const mine = userId !== null && message.sender_id === userId;
            return (
              <div key={message.id} className={mine ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={[
                    "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm",
                    mine ? "rounded-tr-sm bg-astra-gradient text-white" : "rounded-tl-sm border border-base-600 bg-base-800/60 text-ink-100",
                  ].join(" ")}
                >
                  {message.content}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-ink-700">
        <span className={connected ? "text-signal-good" : "text-signal-hold"}>
          {connected ? "Live · real-time" : "Reconnecting…"}
        </span>
      </div>
      {error && <p className="mt-1 text-xs text-signal-reject">{error}</p>}

      <div className="mt-3 flex items-center gap-2 border-t border-base-600 pt-3">
        <button
          aria-label={listening ? "Stop dictation" : "Dictate message"}
          aria-pressed={listening}
          onClick={() => (listening ? stopVoice() : startVoice())}
          className={[
            "grid h-9 w-9 shrink-0 place-items-center rounded-full transition",
            listening ? "bg-astra-gradient text-white" : "bg-base-800 text-ink-300 hover:text-ink-100",
          ].join(" ")}
        >
          {listening ? <Square className="h-3 w-3" /> : <Mic className="h-3.5 w-3.5" />}
        </button>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
          placeholder={listening ? interim || "Listening…" : "Type a message…"}
          className="flex-1 rounded-full border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100 placeholder:text-ink-700 focus:outline-none"
        />
        <button
          aria-label="Send message"
          onClick={() => void send()}
          disabled={sending || !draft.trim()}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-astra-gradient text-white hover:opacity-90 disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

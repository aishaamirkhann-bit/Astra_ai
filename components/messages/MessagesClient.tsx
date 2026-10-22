"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Camera, ImagePlus, LoaderCircle, Mic, Plus, Send, ShieldHalf, Square, X } from "lucide-react";
import ARTryOnModal from "@/components/product/ARTryOnModal";
import CatalogProductImage from "@/components/CatalogProductImage";
import { getChatHistory, getOrdersWebSocketUrl, getProduct, requestOrderReturn, sendMultimodalChat, trackOrders } from "@/lib/api";
import { useSpeechRecognition } from "@/lib/useSpeechRecognition";
import { getARModelForProduct } from "@/lib/arIntent";
import type { ChatBundleCard, ChatCard, ChatConversation, ChatMessage, ChatOperationCard, ChatOutfitCard, ProductDetail } from "@/lib/types";

export default function MessagesClient() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const galleryInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const [pendingImageUrl, setPendingImageUrl] = useState<string | null>(null);
  const [operationResults, setOperationResults] = useState<Record<string, string>>({});
  const [arProduct, setArProduct] = useState<ProductDetail | null>(null);
  const [arLoadingSlug, setArLoadingSlug] = useState<string | null>(null);
  const messageInputRef = useRef<HTMLInputElement | null>(null);

  const { listening, interim, start: startVoice, stop: stopVoice } = useSpeechRecognition({
    onFinal: (text) => setDraft((current) => (current ? `${current} ${text}` : text)),
  });

  const active = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [conversations, activeId],
  );
  const trackedOrderRefs = useMemo(() => (active?.messages ?? [])
    .filter((message) => message.card_type === "order_tracking" && message.card && "order_ref" in message.card)
    .map((message) => (message.card as ChatOperationCard).order_ref)
    .join(","), [active?.messages]);

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
  }, [active?.messages.length, streamingText, pendingUserText, pendingImageUrl]);

  useEffect(() => {
    if (!trackedOrderRefs) return;
    const socket = new WebSocket(getOrdersWebSocketUrl());
    const refs = new Set(trackedOrderRefs.split(","));
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as { type?: string; order_ref?: string };
        if (event.type !== "order_update" || !event.order_ref || !refs.has(event.order_ref)) return;
        void trackOrders("", event.order_ref).then(({ orders }) => {
          const latest = orders[0];
          if (!latest) return;
          setConversations((current) => current.map((conversation) => conversation.id === activeId
            ? { ...conversation, messages: conversation.messages.map((chatMessage) => {
              if (chatMessage.card_type !== "order_tracking" || !chatMessage.card || !("order_ref" in chatMessage.card) || chatMessage.card.order_ref !== latest.order_ref) return chatMessage;
              return { ...chatMessage, card: { ...chatMessage.card, status: latest.status, timeline: latest.timeline } };
            }) }
            : conversation));
        }).catch(() => undefined);
      } catch { /* Ignore non-order notification frames. */ }
    };
    const ping = window.setInterval(() => { if (socket.readyState === WebSocket.OPEN) socket.send("ping"); }, 20000);
    return () => { window.clearInterval(ping); socket.close(); };
  }, [activeId, trackedOrderRefs]);

  useEffect(() => {
    if (!selectedImage) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(selectedImage);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedImage]);

  const send = async () => {
    const text = draft.trim();
    if ((!text && !selectedImage) || sending) return;
    const image = selectedImage;
    setSending(true);
    setDraft("");
    setSelectedImage(null);
    messageInputRef.current?.focus({ preventScroll: true });
    setError(null);
    setPendingUserText(text || "Image attached");
    setPendingImageUrl(previewUrl);
    setStreamingText(image ? "Analyzing your image with ASTRA Vision…" : "Thinking…");
    try {
      const response = await sendMultimodalChat({
        message: text,
        conversation_id: activeId ?? undefined,
        image: image ?? undefined,
      });
      try {
        const history = await getChatHistory();
        setConversations(history);
        setActiveId(response.conversation_id || history[0]?.id || null);
      } catch {
        const fallbackId = response.conversation_id || activeId || -Date.now();
        const now = new Date().toISOString();
        const userMessage: ChatMessage = {
          id: `local-user-${now}`,
          role: "user",
          content: text || "Please describe this image.",
          card_type: image ? "image_attachment" : null,
          card: image ? { filename: image.name } : null,
          created_at: now,
        };
        const assistantMessage: ChatMessage = {
          id: `local-assistant-${now}`,
          role: "assistant",
          content: response.reply_text,
          card_type: response.card_type ?? (response.products.length ? "products" : null),
          card: response.card ?? response.products,
          created_at: now,
        };
        setConversations((current) => {
          const existing = current.find((conversation) => conversation.id === fallbackId);
          if (existing) {
            return current.map((conversation) => conversation.id === fallbackId
              ? { ...conversation, messages: [...conversation.messages, userMessage, assistantMessage] }
              : conversation);
          }
          return [...current, { id: fallbackId, title: (text || "Image question").slice(0, 70), messages: [userMessage, assistantMessage] }];
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
      setPendingImageUrl(null);
    }
  };

  async function confirmReturn(card: ChatOperationCard) {
    const key = `${card.order_ref}:return`;
    setOperationResults((current) => ({ ...current, [key]: "Submitting request for review…" }));
    try {
      const requestType = card.request_type || "return";
      const result = await requestOrderReturn({ order_ref: card.order_ref, request_type: requestType, reason: card.reason || `Buyer requested ${requestType}`, confirmed: true });
      setOperationResults((current) => ({ ...current, [key]: result.message }));
    } catch (cause) {
      setOperationResults((current) => ({ ...current, [key]: cause instanceof Error ? cause.message : "Return request could not be submitted." }));
    }
  }

  async function launchTryOn(slug: string) {
    if (!getARModelForProduct({ slug })) return;
    setArLoadingSlug(slug);
    try {
      setArProduct(await getProduct(slug));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open the product try-on preview.");
    } finally {
      setArLoadingSlug(null);
    }
  }

  function reviewBundle(messageId: number | string) {
    setOperationResults((current) => ({ ...current, [`bundle:${messageId}`]: "Reviewed. This quote is non-binding; standard checkout and financial consent apply to the actual total." }));
  }

  const startNewConversation = () => {
    setActiveId(null);
    setDraft("");
    setSelectedImage(null);
  };

  const chooseImage = (file: File | undefined) => {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Choose a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError("Images must be 8 MB or smaller.");
      return;
    }
    setError(null);
    setSelectedImage(file);
  };

  const renderMessage = (message: ChatMessage, key: string | number) =>
    message.role === "user" ? (
      <div key={key} className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-astra-gradient px-4 py-2.5 text-sm text-white">
          {message.content}
          {message.card_type === "image_attachment" && (
            <span className="mt-2 flex items-center gap-1.5 text-xs text-white/80">
              <ImagePlus className="h-3.5 w-3.5" /> Image attached
            </span>
          )}
        </div>
      </div>
    ) : (
      <div key={key} className="flex items-start gap-2">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
          <ShieldHalf className="h-3.5 w-3.5 text-astra-cyan" />
        </div>
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100">
          {message.content}
          {(() => {
            const cards: ChatCard[] = Array.isArray(message.card)
              ? message.card
              : message.card && "slug" in message.card ? [message.card] : [];
            const operationCard = message.card && "order_ref" in message.card ? message.card as ChatOperationCard : null;
            if (message.card_type === "order_tracking" && operationCard) return (
              <div key={`tracking-${message.id}`} className="mt-3 rounded-xl border border-base-600 bg-base-900/80 p-3">
                <p className="text-xs font-semibold text-ink-100">{operationCard.product_name} · {operationCard.order_ref}</p>
                <ol className="mt-2 grid gap-1 sm:grid-cols-4">{(operationCard.timeline ?? []).map((stage) => <li key={stage.label} className={`rounded-lg px-2 py-1.5 text-[10px] ${stage.status === "done" ? "bg-emerald-500/10 text-emerald-300" : "bg-base-800 text-ink-500"}`}>{stage.label}: {stage.status === "done" ? "Complete" : "Not yet reported"}</li>)}</ol>
              </div>
            );
            if (message.card_type === "return_confirmation" && operationCard) {
              const result = operationResults[`${operationCard.order_ref}:return`];
              return (
                <div key={`return-${message.id}`} className="mt-3 rounded-xl border border-amber-400/25 bg-base-900/80 p-3">
                  <p className="text-xs font-semibold capitalize text-ink-100">{operationCard.request_type || "return"} request · {operationCard.product_name}</p>
                  <p className="mt-1 text-[10px] text-ink-400">{operationCard.explanation}</p>
                  {operationCard.eligible && <button type="button" onClick={() => void confirmReturn(operationCard)} disabled={Boolean(result)} className="mt-2 rounded-lg bg-astra-gradient px-3 py-2 text-[10px] font-semibold capitalize text-white disabled:opacity-50">{result ? "Request sent" : `Confirm ${operationCard.request_type || "return"} request for review`}</button>}
                  {result && <p role="status" className="mt-2 text-[10px] text-emerald-300">{result}</p>}
                  <p className="mt-2 text-[9px] text-ink-600">Submitting creates a review request only; it does not issue a refund or change the order.</p>
                </div>
              );
            }
            const bundleCard = message.card && "offer_total" in message.card ? message.card as ChatBundleCard : null;
            const outfitCard = message.card_type === "outfit_recommendations" && message.card && "outfits" in message.card ? message.card as ChatOutfitCard : null;
            if (outfitCard?.outfits[0]) return <div key={`outfit-${message.id}`} className="mt-3 grid gap-2 sm:grid-cols-2">
              {outfitCard.outfits[0].items.map(({ slot, product, reasons }) => <article key={`${message.id}-${product.id}`} className="flex min-w-0 gap-2 rounded-xl border border-base-600 bg-base-900/70 p-2">
                <div className="h-16 w-14 shrink-0 overflow-hidden rounded-lg"><CatalogProductImage src={product.image_url} title={`${product.title} ${product.color}`} category={product.category} className="h-full w-full object-cover" /></div>
                <div className="min-w-0"><span className="text-[9px] font-semibold uppercase text-cyan-300">{slot}</span><p className="line-clamp-2 text-[11px] font-semibold text-ink-100">{product.title}</p><p className="text-[10px] text-ink-400">Rs. {product.price.toLocaleString()}</p>{reasons.map((reason) => <p key={reason} className="text-[9px] text-ink-500">{reason}</p>)}</div>
              </article>)}
            </div>;
            if (message.card_type === "bundle_advisory" && bundleCard) {
              const review = operationResults[`bundle:${message.id}`];
              return (
                <div key={`bundle-${message.id}`} className="mt-3 rounded-xl border border-violet-400/25 bg-base-900/80 p-3">
                  <ul className="grid gap-1.5">{bundleCard.items.map((line) => <li key={line.product_id} className="flex justify-between gap-2 text-[10px] text-ink-300"><span>{line.title} × {line.quantity} · seller floor Rs. {line.seller_floor.toLocaleString()}</span><span>Rs. {line.line_total.toLocaleString()}</span></li>)}</ul>
                  <p className="mt-2 flex justify-between border-t border-base-700 pt-2 text-[11px] font-bold text-ink-100"><span>Estimate · savings Rs. {bundleCard.estimated_savings.toLocaleString()}</span><span>Rs. {bundleCard.offer_total.toLocaleString()}</span></p>
                  <button type="button" onClick={() => reviewBundle(message.id)} disabled={Boolean(review)} className="mt-2 rounded-lg border border-violet-400/40 px-3 py-2 text-[10px] font-semibold text-violet-200">{review ? "Offer reviewed" : "Review this non-binding offer"}</button>
                  {review && <p role="status" className="mt-2 text-[10px] text-emerald-300">{review}</p>}
                  <p className="mt-2 text-[9px] text-ink-600">No order, cart price, or payment is changed by this estimate.</p>
                </div>
              );
            }
            return cards.length > 0 && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {cards.map((card) => (
                  <article key={card.slug} className="rounded-xl border border-base-600 bg-base-900/70 p-2.5 transition hover:border-astra-indigo">
                    <Link href={`/product/${card.slug}`} className="flex items-center gap-3">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={card.image} alt={card.name} className="h-12 w-12 rounded-lg object-cover" />
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-semibold text-ink-100">{card.name}</span>
                      {card.category && <span className="block truncate text-[10px] text-ink-500">{card.category}</span>}
                      <span className="block text-[10px] text-ink-500">
                        Rs. {card.price.toLocaleString()} · {card.trust}% trust · {card.stock} in stock
                      </span>
                    </span>
                    </Link>
                    {getARModelForProduct({ slug: card.slug }) && (
                      <button
                        type="button"
                        onClick={() => void launchTryOn(card.slug)}
                        disabled={arLoadingSlug === card.slug}
                        className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-astra-violet/40 bg-base-800 px-2.5 py-1.5 text-[10px] font-semibold text-ink-100 transition hover:border-astra-violet hover:text-white disabled:opacity-60"
                      >
                        <Camera className="h-3.5 w-3.5 text-astra-cyan" />
                        {arLoadingSlug === card.slug ? "Opening preview…" : "Try On"}
                      </button>
                    )}
                  </article>
                ))}
              </div>
            );
          })()}
        </div>
      </div>
    );

  return (
    <>
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
                {pendingImageUrl && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={pendingImageUrl} alt="Attached image preview" className="mt-2 max-h-48 max-w-full rounded-xl object-contain" />
                )}
              </div>
            </div>
          )}
          {streamingText !== null && (
            <div className="flex items-start gap-2">
              <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-astra-gradient-soft">
                <ShieldHalf className="h-3.5 w-3.5 text-astra-cyan" />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-tl-sm border border-base-600 bg-base-800/60 px-4 py-2.5 text-sm text-ink-100">
                <span className="inline-flex items-center gap-2">
                  <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                  {streamingText || "…"}
                </span>
              </div>
            </div>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-signal-reject">{error}</p>}

        {previewUrl && (
          <div className="relative mt-4 w-fit rounded-xl border border-base-600 bg-base-900/70 p-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt="Selected image preview" className="h-24 max-w-[180px] rounded-lg object-cover" />
            <button
              type="button"
              aria-label="Remove attached image"
              onClick={() => setSelectedImage(null)}
              className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-base-800 text-ink-100 shadow"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-base-600 pt-4">
          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              chooseImage(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(event) => {
              chooseImage(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
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
          <button
            type="button"
            aria-label="Upload image from gallery"
            title="Choose from gallery"
            onClick={() => galleryInputRef.current?.click()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-base-600 bg-white/70 text-ink-300 transition hover:border-astra-indigo hover:text-astra-indigo"
          >
            <ImagePlus className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Take a photo with camera"
            title="Take a photo"
            onClick={() => cameraInputRef.current?.click()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-base-600 bg-white/70 text-ink-300 transition hover:border-astra-indigo hover:text-astra-indigo"
          >
            <Camera className="h-4 w-4" />
          </button>
          <input
            ref={messageInputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            inputMode="text"
            onPaste={(event) => {
              const pastedImage = Array.from(event.clipboardData.items)
                .find((item) => item.type.startsWith("image/"))?.getAsFile();
              if (!pastedImage) return;
              event.preventDefault();
              chooseImage(pastedImage);
            }}
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
            disabled={sending || (!draft.trim() && !selectedImage)}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-astra-gradient text-white hover:opacity-90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
    {arProduct && <ARTryOnModal product={arProduct} onClose={() => setArProduct(null)} />}
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Handshake, Loader2, Radio, X } from "lucide-react";
import { getA2aNegotiationWebSocketUrl, submitNegotiationOffer } from "@/lib/api";
import { showToast } from "@/lib/toast";
import type { NegotiationRound } from "@/lib/api";

const MAX_ROUNDS = 6;

interface A2aParams {
  buyer_agent: string;
  seller_agent: string;
  buyer_budget: number;
  buyer_opening_offer: number;
  delay_threshold_ms: number;
  seller_ask: number;
  seller_floor: number;
  market_average: number;
  max_rounds: number;
}

interface A2aFeedEntry {
  key: number;
  side: "buyer" | "seller" | "system";
  label: string;
  amount?: number;
  message: string;
}

/** Real-time buyer/seller agent counter-offer room + A2A live negotiation. */
export default function NegotiatorModal({
  open,
  productId,
  productName,
  listPrice,
  onClose,
}: {
  open: boolean;
  productId: string;
  productName: string;
  listPrice: number;
  onClose: () => void;
}) {
  const [rounds, setRounds] = useState<NegotiationRound[]>([]);
  const [offer, setOffer] = useState("");
  const [autoMode, setAutoMode] = useState(true);
  const [busy, setBusy] = useState(false);
  const [settled, setSettled] = useState<NegotiationRound | null>(null);
  const sessionIdRef = useRef<number | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const [a2aActive, setA2aActive] = useState(false);
  const [a2aParams, setA2aParams] = useState<A2aParams | null>(null);
  const [a2aFeed, setA2aFeed] = useState<A2aFeedEntry[]>([]);
  const [a2aProgress, setA2aProgress] = useState(0);
  const [a2aResult, setA2aResult] = useState<{ finalPrice: number; rounds: number; savings: number } | null>(null);
  const a2aSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!open) {
      setRounds([]);
      setOffer("");
      setSettled(null);
      sessionIdRef.current = null;
      setBusy(false);
      setA2aActive(false);
      setA2aParams(null);
      setA2aFeed([]);
      setA2aProgress(0);
      setA2aResult(null);
      a2aSocketRef.current?.close();
      a2aSocketRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [rounds.length, a2aFeed.length]);

  if (!open) return null;

  const playRound = async (offerPrice: number, round: number): Promise<NegotiationRound | null> => {
    try {
      const result = await submitNegotiationOffer(productId, {
        offer_price: offerPrice,
        round,
        ...(sessionIdRef.current ? { session_id: sessionIdRef.current } : {}),
      });
      sessionIdRef.current = result.session_id;
      setRounds((current) => [...current, result]);
      if (result.status === "accepted") {
        setSettled(result);
        showToast(`Deal settled at Rs. ${(result.final_price ?? 0).toLocaleString()}!`, "success");
      } else if (result.status === "rejected") {
        setSettled(result);
        showToast("Seller agent walked away from this negotiation.", "error");
      }
      return result;
    } catch (requestError) {
      showToast((requestError as Error).message || "Negotiation service unavailable.", "error");
      return null;
    }
  };

  const runAuto = async (firstOffer: number) => {
    setBusy(true);
    let nextOffer = firstOffer;
    for (let round = rounds.length + 1; round <= MAX_ROUNDS; round += 1) {
      const result = await playRound(nextOffer, round);
      if (!result || result.status !== "counter" || !result.counter_offer) break;
      nextOffer = Math.round(result.counter_offer * 0.985);
    }
    setBusy(false);
  };

  const start = async () => {
    const first = Number(offer);
    if (!first || first <= 0) return;
    setOffer("");
    setBusy(true);
    if (autoMode) {
      await runAuto(first);
    } else {
      await playRound(first, rounds.length + 1);
    }
    setBusy(false);
  };

  const launchA2a = () => {
    if (a2aActive || a2aResult) return;
    setA2aActive(true);
    setA2aFeed([]);
    const socket = new WebSocket(getA2aNegotiationWebSocketUrl(productId));
    a2aSocketRef.current = socket;
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, unknown>;
        if (payload.type === "a2a_started") {
          setA2aParams(payload.params as A2aParams);
          setA2aFeed((feed) => [...feed, { key: feed.length, side: "system", label: "A2A channel", message: "Buyer & seller agents connected — target parameters exchanged." }]);
        } else if (payload.type === "buyer_offer" || payload.type === "seller_counter") {
          const buyer = payload.type === "buyer_offer";
          setA2aProgress(Number(payload.progress ?? 0));
          setA2aFeed((feed) => [...feed, {
            key: feed.length,
            side: buyer ? "buyer" : "seller",
            label: `R${payload.round} · ${buyer ? "ASTRA-Buyer" : "Seller-Agent"}`,
            amount: Number(buyer ? payload.offer : payload.ask),
            message: String(payload.message ?? ""),
          }]);
        } else if (payload.type === "deal_settled") {
          setA2aProgress(1);
          setA2aResult({ finalPrice: Number(payload.final_price), rounds: Number(payload.rounds), savings: Number(payload.savings_vs_list) });
          setA2aActive(false);
          showToast(`A2A deal settled at Rs. ${Number(payload.final_price).toLocaleString()}!`, "success");
        }
      } catch {
        // Ignore malformed frames — the room keeps streaming.
      }
    };
    socket.onclose = () => setA2aActive(false);
    socket.onerror = () => {
      setA2aActive(false);
      showToast("A2A negotiation channel unavailable.", "error");
    };
  };

  return (
    <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/75 p-4 backdrop-blur-sm" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="glass flex max-h-[88vh] w-full max-w-lg flex-col rounded-3xl p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-violet-400">
              <Handshake className="h-3 w-3" /> AI Negotiator
            </p>
            <h2 className="mt-1 font-display text-lg font-bold text-ink-100">{productName}</h2>
            <p className="text-[11px] text-ink-500">List price Rs. {listPrice.toLocaleString()} · buyer & seller agents bargain in real time</p>
          </div>
          <button onClick={onClose} aria-label="Close negotiator" className="rounded-full bg-base-800 p-2 text-ink-300 hover:text-ink-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 rounded-xl border border-violet-400/25 bg-base-900/70 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
              <Radio className={`h-3 w-3 ${a2aActive ? "animate-pulse text-rose-400" : "text-violet-300"}`} />
              Agent-to-Agent Live Room
            </p>
            {!a2aActive && !a2aResult && (
              <button onClick={launchA2a} className="rounded-lg bg-astra-gradient px-3 py-1.5 text-[10px] font-bold text-white">Launch A2A negotiation</button>
            )}
            {a2aResult && (
              <span className="rounded-full bg-signal-good/10 px-2.5 py-1 text-[10px] font-bold text-signal-good">
                DEAL SETTLED · Rs. {a2aResult.finalPrice.toLocaleString()}
              </span>
            )}
          </div>
          {a2aParams && (
            <div className="mt-2 grid grid-cols-2 gap-1.5 text-[9px] text-ink-500 sm:grid-cols-4">
              <span className="rounded-lg bg-base-800 px-2 py-1">Buyer budget <b className="text-ink-100">Rs. {a2aParams.buyer_budget.toLocaleString()}</b></span>
              <span className="rounded-lg bg-base-800 px-2 py-1">Delay threshold <b className="text-ink-100">{a2aParams.delay_threshold_ms}ms</b></span>
              <span className="rounded-lg bg-base-800 px-2 py-1">Seller floor <b className="text-ink-100">Rs. {a2aParams.seller_floor.toLocaleString()}</b></span>
              <span className="rounded-lg bg-base-800 px-2 py-1">Max rounds <b className="text-ink-100">{a2aParams.max_rounds}</b></span>
            </div>
          )}
          {(a2aActive || a2aFeed.length > 0) && (
            <>
              <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-base-700">
                <div className="h-full rounded-full bg-astra-gradient transition-all duration-500" style={{ width: `${Math.round(a2aProgress * 100)}%` }} />
              </div>
              <p className="mt-1 text-right text-[9px] text-ink-700">agreement proximity {Math.round(a2aProgress * 100)}%</p>
              <ul className="scroll-thin mt-1 flex max-h-32 flex-col gap-1.5 overflow-y-auto pr-1">
                {a2aFeed.map((entry) => (
                  <li key={entry.key} className={`flex items-start gap-2 text-[10px] leading-relaxed ${entry.side === "system" ? "text-ink-700" : "text-ink-300"}`}>
                    <span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[8px] font-bold uppercase ${entry.side === "buyer" ? "bg-cyan-500/10 text-cyan-400" : entry.side === "seller" ? "bg-violet-500/10 text-violet-400" : "bg-base-800 text-ink-700"}`}>
                      {entry.label}
                    </span>
                    <span>
                      {entry.amount !== undefined && <b className="text-ink-100">Rs. {entry.amount.toLocaleString()}</b>}
                      {entry.amount !== undefined && " — "}
                      {entry.message}
                    </span>
                  </li>
                ))}
                {a2aResult && (
                  <li className="rounded-lg bg-signal-good/10 px-2 py-1.5 text-[10px] font-semibold text-signal-good">
                    Handshake complete in {a2aResult.rounds} rounds — saved Rs. {a2aResult.savings.toLocaleString()} off list price.
                  </li>
                )}
              </ul>
            </>
          )}
        </div>

        <div ref={scrollRef} className="scroll-thin mt-4 flex min-h-[180px] flex-1 flex-col gap-3 overflow-y-auto pr-1">
          {rounds.length === 0 && !busy && (
            <p className="m-auto text-center text-xs text-ink-700">
              Apni opening offer likhein — AI seller agent counter karega.
            </p>
          )}
          {rounds.map((round) => (
            <div key={round.round} className="rounded-xl border border-base-600 bg-base-900/60 p-3">
              <div className="flex items-center justify-between text-[10px] font-semibold text-ink-500">
                <span className="flex items-center gap-1"><Bot className="h-3 w-3 text-astra-cyan" /> Round {round.round}</span>
                <span className={round.status === "accepted" ? "text-signal-good" : round.status === "rejected" ? "text-signal-reject" : "text-signal-hold"}>
                  {round.status.toUpperCase()}
                </span>
              </div>
              <p className="mt-1.5 text-[11px] text-ink-300">
                Seller ask Rs. {round.seller_ask.toLocaleString()}
                {round.counter_offer ? ` · counter Rs. ${round.counter_offer.toLocaleString()}` : ""}
                {round.final_price ? ` · settled Rs. ${round.final_price.toLocaleString()}` : ""}
              </p>
              <ul className="mt-2 flex flex-col gap-1">
                {round.reasoning.map((line, index) => (
                  <li key={index} className="text-[10px] leading-relaxed text-ink-700">• {line}</li>
                ))}
              </ul>
            </div>
          ))}
          {busy && <p className="text-center text-[11px] text-ink-500">Agents negotiating…</p>}
        </div>

        {!settled && (
          <div className="mt-4 border-t border-base-600 pt-4">
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                value={offer}
                onChange={(e) => setOffer(e.target.value)}
                placeholder="Your offer (Rs.)"
                className="flex-1 rounded-xl border border-base-600 bg-base-900 px-4 py-2.5 text-xs text-ink-100"
              />
              <button
                onClick={() => void start()}
                disabled={busy || !Number(offer)}
                className="rounded-xl bg-astra-gradient px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Send offer"}
              </button>
            </div>
            <label className="mt-2 flex items-center gap-2 text-[10px] text-ink-500">
              <input type="checkbox" checked={autoMode} onChange={(e) => setAutoMode(e.target.checked)} className="accent-violet-500" />
              AI auto-negotiate: buyer agent counter-offers until deal settles
            </label>
          </div>
        )}
      </section>
    </div>
  );
}

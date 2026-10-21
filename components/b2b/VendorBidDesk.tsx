"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { getB2BBidRequests, getVendorB2BQuotes, placeB2BVendorQuote, type B2BBidRequest, type B2BQuote } from "@/lib/api";

const money = (amount: number) => `Rs. ${Math.round(amount).toLocaleString("en-PK")}`;

export default function VendorBidDesk() {
  const [requests, setRequests] = useState<B2BBidRequest[]>([]);
  const [quotes, setQuotes] = useState<Array<B2BQuote & { request: B2BBidRequest }>>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [open, own] = await Promise.all([getB2BBidRequests(), getVendorB2BQuotes()]);
      setRequests(open); setQuotes(own); setError("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load supplier opportunities."); }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);
  const quotedBidIds = new Set(quotes.filter((quote) => quote.status === "submitted").map((quote) => quote.bid_id));

  async function submitQuote(event: FormEvent<HTMLFormElement>, bid: B2BBidRequest) {
    event.preventDefault(); const formElement = event.currentTarget; const values = new FormData(formElement);
    setBusyId(bid.id); setError(""); setNotice("");
    try {
      const featured = values.get("featured") === "on";
      const offeredPrice = Number(values.get("price"));
      const quote = await placeB2BVendorQuote({ bid_id: bid.id, offered_price: offeredPrice, delivery_days: Number(values.get("days")), is_featured: featured });
      setNotice(`Quote submitted. ${quote.commission_rate * 100}% platform commission estimate: ${money(quote.commission_amount)}; estimated net: ${money(quote.vendor_net_payout)}.`);
      formElement.reset(); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not submit this quote."); }
    finally { setBusyId(null); }
  }

  return <div className="space-y-6">
    <section className="rounded-2xl border border-violet-300/20 bg-gradient-to-br from-violet-500/10 to-cyan-500/5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-200">Supplier marketplace</p><h2 className="mt-1 font-display text-lg font-bold text-ink-100">Buyer requests open for quotes</h2><p className="mt-1 text-xs text-ink-400">Submit your total offer and delivery time. Commission and estimated net are shown before submission.</p></div><Link href="/pricing" className="rounded-lg border border-base-600 px-3 py-2 text-[10px] font-semibold text-ink-200 hover:bg-base-800">View vendor plans</Link></div>
    </section>
    {error && <p role="alert" className="rounded-lg border border-rose-400/20 bg-rose-400/5 p-3 text-xs text-rose-300">{error}</p>}
    {notice && <p role="status" className="rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-3 text-xs text-emerald-300">{notice}</p>}
    {requests.length === 0 && <p className="rounded-xl border border-base-700 bg-base-900/50 p-4 text-xs text-ink-500">There are no open buyer requests at the moment.</p>}
    <div className="grid gap-4 lg:grid-cols-2">{requests.map((bid) => <article key={bid.id} className="rounded-2xl border border-base-700 bg-base-900/60 p-4">
      <div className="flex items-start justify-between gap-3"><div><span className="rounded-full bg-cyan-400/10 px-2 py-1 text-[9px] font-semibold text-cyan-200">{bid.category}</span><h3 className="mt-2 text-sm font-semibold text-ink-100">{bid.title}</h3></div><span className="text-right text-[10px] text-ink-400">Target {money(bid.target_budget)}<br />{bid.delivery_days} days max</span></div>
      {bid.description && <p className="mt-2 text-xs text-ink-400">{bid.description}</p>}
      <p className="mt-2 text-[10px] text-ink-500">Quantity requested: {bid.quantity.toLocaleString()}</p>
      {quotedBidIds.has(bid.id) ? <p className="mt-3 rounded-lg bg-emerald-400/5 p-3 text-xs text-emerald-300">You’ve submitted a quote for this request.</p> : <form onSubmit={(event) => void submitQuote(event, bid)} className="mt-4 grid gap-3 rounded-xl border border-base-700 bg-base-800/60 p-3">
        <div className="grid grid-cols-2 gap-2"><label className="text-[10px] text-ink-400">Total offered price (PKR)<input name="price" type="number" required min="1" step="0.01" className="mt-1 w-full rounded-lg border border-base-600 bg-base-900 px-2.5 py-2 text-xs text-ink-100" /></label><label className="text-[10px] text-ink-400">Delivery days<input name="days" type="number" required min="1" max="730" defaultValue={bid.delivery_days} className="mt-1 w-full rounded-lg border border-base-600 bg-base-900 px-2.5 py-2 text-xs text-ink-100" /></label></div>
        <label className="flex items-start gap-2 rounded-lg border border-base-700 px-3 py-2.5 text-[10px] text-ink-300"><input name="featured" type="checkbox" className="mt-0.5 accent-violet-500" /><span><strong className="text-amber-200">Promoted / Featured Listing</strong><br />Adds a featured badge and uses the 2% commission estimate (standard quote: 1%).</span></label>
        <button disabled={busyId === bid.id} className="rounded-lg bg-astra-gradient px-3 py-2.5 text-[11px] font-bold text-white disabled:opacity-50">{busyId === bid.id ? "Submitting…" : "Submit supplier quote"}</button>
      </form>}
    </article>)}</div>
    {quotes.length > 0 && <section><h2 className="font-display text-sm font-bold text-ink-100">Your recent quotes</h2><div className="mt-2 grid gap-2 md:grid-cols-2">{quotes.slice(0, 6).map((quote) => <article key={quote.id} className="rounded-xl border border-base-700 bg-base-900/50 p-3"><div className="flex justify-between gap-2"><p className="truncate text-xs font-semibold text-ink-100">{quote.request.title}</p><span className="text-[10px] text-emerald-300">Match {quote.ai_match_score}%</span></div><p className="mt-1 text-[10px] text-ink-400">{money(quote.offered_price)} · estimated net {money(quote.vendor_net_payout)} · {quote.delivery_days} days · {quote.status}</p></article>)}</div></section>}
  </div>;
}

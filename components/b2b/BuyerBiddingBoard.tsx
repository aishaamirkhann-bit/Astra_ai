"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { awardB2BVendorQuote, createB2BBidRequest, getB2BBidRequests, type B2BBidRequest } from "@/lib/api";

const money = (value: number) => `Rs. ${Math.round(value).toLocaleString("en-PK")}`;

export default function BuyerBiddingBoard() {
  const [requests, setRequests] = useState<B2BBidRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [awardingQuoteId, setAwardingQuoteId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    try { setRequests(await getB2BBidRequests()); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load your buyer requests."); }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 20_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await createB2BBidRequest({
        title: String(form.get("title")), description: String(form.get("description") ?? ""),
        category: String(form.get("category")), quantity: Number(form.get("quantity")),
        target_budget: Number(form.get("budget")), delivery_days: Number(form.get("days")), closes_at: null,
      });
      formElement.reset(); setNotice("Request published. Suppliers can now submit quotes."); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not publish the request."); }
    finally { setBusy(false); }
  }

  async function awardQuote(request: B2BBidRequest, quoteId: number) {
    if (!window.confirm("Select this supplier? This records your selection only; it does not create an order or process payment.")) return;
    setAwardingQuoteId(quoteId); setError(""); setNotice("");
    try {
      const result = await awardB2BVendorQuote(request.id, quoteId);
      setNotice(`Supplier selected. Request status: ${result.bid_status}. No order or payment was created.`);
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not select this supplier."); }
    finally { setAwardingQuoteId(null); }
  }

  return <div className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.5fr)]">
    <section className="rounded-2xl border border-base-700 bg-base-900/70 p-5">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-300">Buyer request</p>
      <h2 className="mt-1 font-display text-lg font-bold text-ink-100">Request supplier bids</h2>
      <p className="mt-1 text-xs leading-relaxed text-ink-500">Set the quantity, target budget, and required delivery window. A request does not create an order or authorize payment.</p>
      <form onSubmit={submit} className="mt-4 grid gap-3">
        <label className="text-[11px] text-ink-400">Request title<input name="title" required minLength={3} maxLength={160} placeholder="e.g. Wholesale cotton shirts" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
        <label className="text-[11px] text-ink-400">Category<input name="category" required minLength={2} maxLength={80} placeholder="Apparel" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
        <label className="text-[11px] text-ink-400">Details<textarea name="description" maxLength={4000} rows={3} placeholder="Sizes, quality, or packaging needs" className="mt-1 w-full resize-y rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[11px] text-ink-400">Quantity<input name="quantity" type="number" required min={1} defaultValue={100} className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
          <label className="text-[11px] text-ink-400">Target budget (PKR)<input name="budget" type="number" required min={1} step="0.01" placeholder="150000" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
        </div>
        <label className="text-[11px] text-ink-400">Maximum delivery time (days)<input name="days" type="number" required min={1} max={730} defaultValue={14} className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-sm text-ink-100" /></label>
        {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}{notice && <p role="status" className="text-xs text-emerald-300">{notice}</p>}
        <button disabled={busy} className="rounded-xl bg-astra-gradient px-4 py-3 text-xs font-bold text-white disabled:opacity-50">{busy ? "Publishing…" : "Publish request"}</button>
      </form>
    </section>

    <section className="space-y-3">
      <div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-violet-300">AI bid comparison</p><h2 className="mt-1 font-display text-lg font-bold text-ink-100">Your open requests and supplier quotes</h2></div>
      {requests.length === 0 && <p className="rounded-xl border border-base-700 bg-base-900/50 p-4 text-xs text-ink-500">No open requests yet. Publish a request to invite supplier quotes.</p>}
      {requests.map((request) => <article key={request.id} className="rounded-2xl border border-base-700 bg-base-900/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-ink-100">{request.title}</h3><p className="mt-1 text-[10px] text-ink-500">{request.category} · {request.quantity.toLocaleString()} units · {request.delivery_days} days max</p></div><span className="rounded-full bg-base-800 px-3 py-1 text-[10px] text-ink-300">Budget {money(request.target_budget)}</span></div>
        <p className="mt-1 text-[10px] text-ink-500">Request status: <span className="capitalize text-ink-300">{request.status}</span></p>
        {request.description && <p className="mt-2 text-xs text-ink-400">{request.description}</p>}
        {request.quotes.length === 0 ? <p className="mt-4 rounded-lg bg-base-800/70 p-3 text-[11px] text-ink-500">Waiting for suppliers. Quotes will appear here as they arrive.</p> : <div className="mt-3 grid gap-2 md:grid-cols-2">
          {[...request.quotes].sort((a, b) => b.ai_match_score - a.ai_match_score).map((quote) => <div key={quote.id} className={`rounded-xl border p-3 ${quote.is_featured ? "border-amber-300/40 bg-amber-300/5" : "border-base-700 bg-base-800/60"}`}>
            <div className="flex items-center justify-between gap-2"><p className="truncate text-xs font-semibold text-ink-100">{quote.vendor_name}</p>{quote.is_featured && <span className="rounded-full bg-amber-300/10 px-2 py-1 text-[9px] font-bold text-amber-200">Featured</span>}</div>
            <p className="mt-2 font-display text-lg font-bold text-white">{money(quote.offered_price)}</p>
            <div className="mt-2 flex items-center justify-between text-[10px] text-ink-400"><span>{quote.delivery_days} day delivery</span><span className="font-semibold text-emerald-300">AI match {quote.ai_match_score}%</span></div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-base-700"><div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-violet-400" style={{ width: `${quote.ai_match_score}%` }} /></div>
            <p className="mt-2 text-[10px] text-ink-500">Platform commission estimate: {money(quote.commission_amount)} ({quote.commission_rate * 100}%). Vendor estimated net: {money(quote.vendor_net_payout)}.</p>
            {request.status === "open" && quote.status === "submitted" && <button type="button" disabled={awardingQuoteId !== null} onClick={() => void awardQuote(request, quote.id)} className="mt-3 w-full rounded-lg border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-[10px] font-semibold text-emerald-200 disabled:opacity-50">{awardingQuoteId === quote.id ? "Selecting…" : "Select supplier"}</button>}
            {quote.status === "awarded" && <p className="mt-3 rounded-lg bg-emerald-300/10 px-3 py-2 text-center text-[10px] font-semibold text-emerald-200">Selected supplier</p>}
          </div>)}
        </div>}
        <p className="mt-3 text-[9px] text-ink-600">AI score compares quoted price and delivery time with your request. Review terms before any purchase; no order or payment is started here.</p>
      </article>)}
    </section>
  </div>;
}

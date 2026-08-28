"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, CheckCircle2, ChevronDown, Radar, Search, Send, SlidersHorizontal, X } from "lucide-react";
import DealCard from "@/components/deals/DealCard";
import DealQuickView from "@/components/deals/DealQuickView";
import { getDealDetails, getDeals, getDealsWebSocketUrl, reserveDeal } from "@/lib/api";
import type { DealDetail, DealOut } from "@/lib/types";

type Category = "All" | DealOut["category"];
type Sort = "discount" | "trust" | "price";

const categories: Category[] = ["All", "Tech", "Fashion", "Audio", "Accessories"];
const sortLabels: Record<Sort, string> = {
  discount: "Highest Discount %",
  trust: "Top Trust Score",
  price: "Lowest Price",
};

export default function DealsClient({ initialDeals }: { initialDeals: DealOut[] }) {
  const [liveDeals, setLiveDeals] = useState(initialDeals);
  const [category, setCategory] = useState<Category>("All");
  const [sort, setSort] = useState<Sort>("discount");
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [prompt, setPrompt] = useState("");
  const [selectedDeal, setSelectedDeal] = useState<DealDetail | null>(null);
  const [loadingDealId, setLoadingDealId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"cart" | "reserve" | null>(null);
  const [notice, setNotice] = useState("");

  const deals = useMemo(() => {
    const filtered = liveDeals.filter((deal) => (category === "All" || deal.category === category) && (maxPrice === null || deal.price <= maxPrice));
    return [...filtered].sort((a, b) => sort === "discount" ? b.discount_percent - a.discount_percent : sort === "trust" ? b.trust.overall - a.trust.overall : a.price - b.price);
  }, [category, liveDeals, maxPrice, sort]);

  useEffect(() => {
    const socket = new WebSocket(getDealsWebSocketUrl());
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string; deal_id?: string; stock_remaining?: number };
      if (!["deal_updated", "stock_changed", "deal_expired"].includes(event.type ?? "")) return;
      void getDeals().then(setLiveDeals).catch(() => undefined);
      setSelectedDeal((current) => {
        if (!current || current.id !== event.deal_id) return current;
        if (event.type === "deal_expired") return null;
        return typeof event.stock_remaining === "number" ? { ...current, stock_remaining: event.stock_remaining } : current;
      });
    };
    const ping = window.setInterval(() => { if (socket.readyState === WebSocket.OPEN) socket.send("ping"); }, 20000);
    return () => { window.clearInterval(ping); socket.close(); };
  }, []);

  function submitPrompt(event: FormEvent) {
    event.preventDefault();
    const normalized = prompt.toLowerCase();
    const amount = normalized.match(/(?:rs\.?\s*)?([\d,]+)(?:k)?/i);
    if (amount) {
      const raw = Number(amount[1].replaceAll(",", ""));
      setMaxPrice(normalized.includes("k") && raw < 1000 ? raw * 1000 : raw);
    }
    if (/phone|laptop|tech/.test(normalized)) setCategory("Tech");
    else if (/fashion|dress|makeup/.test(normalized)) setCategory("Fashion");
    else if (/audio|headphone|watch/.test(normalized)) setCategory("Audio");
    else if (/jewel|accessor/.test(normalized)) setCategory("Accessories");
    setNotice("Astra refined the live deal feed from your prompt.");
  }

  async function openDeal(deal: DealOut) {
    setLoadingDealId(deal.id);
    try {
      setSelectedDeal(await getDealDetails(deal.id));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Deal details are temporarily unavailable.");
    } finally {
      setLoadingDealId(null);
    }
  }

  async function handleAction(deal: DealDetail, action: "cart" | "reserve", selection = { quantity: 1, size: deal.sizes[0], color: deal.colors[0] }) {
    setBusyAction(action);
    try {
      if (action === "cart") {
        setNotice(`${deal.name} added to your Astra cart.`);
      } else {
        const response = await reserveDeal(deal.id, selection);
        setNotice(response.message);
        setSelectedDeal({ ...deal, stock_remaining: response.stock_remaining });
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Astra could not complete that action.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="relative pb-28">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl2 border border-emerald-500/20 bg-emerald-500/5 p-4">
        <div className="flex items-center gap-3"><span className="relative grid h-10 w-10 place-items-center rounded-xl bg-emerald-500/15"><Radar className="h-5 w-5 text-emerald-500" /><i className="absolute right-1 top-1 h-2 w-2 animate-pulseDot rounded-full bg-emerald-400" /></span><div><p className="text-xs font-semibold text-ink-100">Live Market Scan Active</p><p className="mt-0.5 text-[10px] text-ink-500">{liveDeals.length} listings passed price and trust verification</p></div></div>
        <div className="flex items-center gap-2 text-[10px] text-ink-500"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> ≥15% below market · Trust score ≥75</div>
      </div>

      <div className="sticky top-0 z-30 mb-6 rounded-xl2 border border-base-600 bg-base-950/90 p-2.5 shadow-card backdrop-blur-xl">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="scroll-thin flex gap-1 overflow-x-auto">
            {categories.map((item) => <button key={item} type="button" onClick={() => setCategory(item)} className={`whitespace-nowrap rounded-full px-4 py-2 text-xs font-semibold transition ${category === item ? "bg-astra-gradient text-white shadow-glow" : "text-ink-500 hover:bg-base-800 hover:text-ink-100"}`}>{item}</button>)}
          </div>
          <div className="flex items-center gap-2">
            {maxPrice !== null && <button type="button" onClick={() => setMaxPrice(null)} className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-2 text-[10px] font-semibold text-emerald-600 dark:text-emerald-300">Under Rs. {maxPrice.toLocaleString()} <X className="h-3 w-3" /></button>}
            <div className="relative min-w-48"><SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-500" /><select value={sort} onChange={(event) => setSort(event.target.value as Sort)} className="w-full appearance-none rounded-full border border-base-600 bg-base-800 py-2 pl-9 pr-8 text-xs font-medium text-ink-100 focus:outline-none"><option value="discount">Highest Discount %</option><option value="trust">Top Trust Score</option><option value="price">Lowest Price</option></select><ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-500" /></div>
          </div>
        </div>
      </div>

      <div className="mb-4 flex items-end justify-between"><div><p className="font-display text-lg font-semibold text-ink-100">{category === "All" ? "AI-verified deals" : `${category} deals`}</p><p className="mt-1 text-xs text-ink-500">Sorted by {sortLabels[sort].toLowerCase()}</p></div><span className="font-mono text-xs text-ink-500">{deals.length} results</span></div>
      <motion.div layout className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AnimatePresence mode="popLayout">
          {deals.map((deal) => <DealCard key={deal.id} deal={deal} onOpen={(item) => void openDeal(item)} onQuickAdd={(item) => { setNotice(`${item.name} added to your Astra cart.`); }} />)}
        </AnimatePresence>
      </motion.div>
      {deals.length === 0 && <div className="glass rounded-xl2 p-10 text-center"><Search className="mx-auto h-6 w-6 text-ink-500" /><p className="mt-3 text-sm font-semibold text-ink-100">No verified deals match this request</p><button type="button" onClick={() => { setCategory("All"); setMaxPrice(null); }} className="mt-3 text-xs font-semibold text-astra-cyan">Reset AI filters</button></div>}

      <motion.form onSubmit={submitPrompt} initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="fixed bottom-5 right-5 z-40 w-[calc(100%-2.5rem)] max-w-md rounded-2xl border border-violet-500/30 bg-slate-950/95 p-2 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-2"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-violet-500/15"><Bot className="h-4 w-4 text-violet-300" /></span><input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder='Try “active deals under Rs. 30,000”' className="min-w-0 flex-1 bg-transparent text-xs text-white placeholder:text-slate-500 focus:outline-none" aria-label="Ask Astra to filter deals" /><button type="submit" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-astra-gradient text-white" aria-label="Search deals with Astra"><Send className="h-4 w-4" /></button></div>
      </motion.form>

      <AnimatePresence>{notice && <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed bottom-24 right-5 z-[60] flex max-w-sm items-start gap-2 rounded-xl border border-emerald-500/20 bg-slate-950 p-3 text-xs text-slate-100 shadow-2xl"><CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" /><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Dismiss notification"><X className="h-3.5 w-3.5 text-slate-500" /></button></motion.div>}</AnimatePresence>
      <AnimatePresence>{loadingDealId && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 grid place-items-center bg-slate-950/55 backdrop-blur-sm"><div className="flex items-center gap-3 rounded-xl bg-slate-950 px-5 py-4 text-xs text-white shadow-2xl"><Radar className="h-4 w-4 animate-spin text-violet-400" /> Loading live deal intelligence…</div></motion.div>}</AnimatePresence>
      <DealQuickView deal={selectedDeal} onClose={() => setSelectedDeal(null)} onAction={(deal, action, selection) => void handleAction(deal, action, selection)} busyAction={busyAction} />
    </div>
  );
}

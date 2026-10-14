"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDollarSign, Package, ShieldCheck, Target, TrendingUp } from "lucide-react";
import PageShell from "@/components/PageShell";
import SellerInventoryForm from "@/components/seller/SellerInventoryForm";
import SellerEscrowOrders from "@/components/seller/SellerEscrowOrders";
import DirectMessagesPanel from "@/components/messaging/DirectMessagesPanel";
import {
  createSellerGoal,
  getNotifications,
  getSellerDashboardStats,
  getSellerGoals,
  getSellerInventory,
  getSellerWallet,
  updateSellerInventory,
  type SellerDashboardStats,
  type SellerGoalData,
  type SellerInventoryItem,
  type SellerWalletData,
} from "@/lib/api";
import type { AstraNotification } from "@/lib/types";

export type SellerPageSection =
  | "inventory" | "products" | "orders" | "astra-check" | "sales-goals"
  | "wallet" | "fulfillment" | "notifications" | "messages";

const PAGE: Record<SellerPageSection, { label: string; title: string; subtitle: string }> = {
  inventory: { label: "My Inventory", title: "Inventory Management", subtitle: "Add listings by barcode and keep stock accurate." },
  products: { label: "Products", title: "Product Catalog", subtitle: "Review catalog listings, pricing, and available stock." },
  orders: { label: "Orders", title: "Order Processing", subtitle: "Review buyer orders and act on eligible fulfillment steps." },
  "astra-check": { label: "ASTRA Check", title: "Trust & Compliance", subtitle: "Review your seller trust indicators and product verification guidance." },
  "sales-goals": { label: "Sales Goals", title: "Sales Goals", subtitle: "Create targets and track progress against your seller goals." },
  wallet: { label: "Wallet", title: "Seller Earnings", subtitle: "View settled order revenue and wallet ledger information." },
  fulfillment: { label: "Fulfillment", title: "Fulfillment Pipeline", subtitle: "Track order states and dispatch eligible orders." },
  notifications: { label: "Notifications", title: "Seller Notifications", subtitle: "Stay on top of ASTRA account and order alerts." },
  messages: { label: "Messages", title: "Buyer Messages", subtitle: "Respond to buyer product questions and conversations." },
};

const money = (value: number) => `Rs. ${Math.round(value).toLocaleString("en-PK")}`;

export default function SellerSectionPage({ section }: { section: SellerPageSection }) {
  const page = PAGE[section];
  const [inventory, setInventory] = useState<SellerInventoryItem[]>([]);
  const [stats, setStats] = useState<SellerDashboardStats | null>(null);
  const [wallet, setWallet] = useState<SellerWalletData | null>(null);
  const [goals, setGoals] = useState<SellerGoalData[]>([]);
  const [notifications, setNotifications] = useState<AstraNotification[]>([]);
  const [error, setError] = useState("");
  const [goalName, setGoalName] = useState("");
  const [goalTarget, setGoalTarget] = useState("");
  const [savingGoal, setSavingGoal] = useState(false);
  const [updatingProduct, setUpdatingProduct] = useState<string | null>(null);

  async function toggleProductStatus(product: SellerInventoryItem) {
    setUpdatingProduct(product.id);
    setError("");
    try {
      await updateSellerInventory(product.id, { status: product.status === "inactive" ? "active" : "inactive" });
      setInventory((current) => current.map((item) => item.id === product.id ? { ...item, status: product.status === "inactive" ? "active" : "inactive" } : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update listing status.");
    } finally {
      setUpdatingProduct(null);
    }
  }

  useEffect(() => {
    let active = true;
    const tasks: Promise<void>[] = [];
    if (section === "products") tasks.push(getSellerInventory().then((value) => { if (active) setInventory(value); }));
    if (section === "astra-check") tasks.push(getSellerDashboardStats().then((value) => { if (active) setStats(value); }));
    if (section === "wallet") tasks.push(getSellerWallet().then((value) => { if (active) setWallet(value); }));
    if (section === "sales-goals") tasks.push(getSellerGoals().then((value) => { if (active) setGoals(value); }));
    if (section === "notifications") tasks.push(getNotifications().then((value) => { if (active) setNotifications(value.items); }));
    void Promise.all(tasks).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not load seller workspace data.");
    });
    return () => { active = false; };
  }, [section]);

  async function submitGoal(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSavingGoal(true);
    try {
      const created = await createSellerGoal({ name: goalName, target_amount: Number(goalTarget) });
      setGoals((current) => [created, ...current]);
      setGoalName("");
      setGoalTarget("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create sales goal.");
    } finally {
      setSavingGoal(false);
    }
  }

  return (
    <PageShell active={page.label} title={page.title} subtitle={page.subtitle}>
      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">{error}</p>}
      {section === "inventory" && <SellerInventoryForm />}
      {section === "products" && (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {inventory.map((product) => (
            <article key={product.id} className="overflow-hidden rounded-2xl border border-purple-100/70 bg-white/75 shadow-sm">
              <img src={product.image_url} alt={product.title} className="h-44 w-full bg-violet-50 object-contain p-3" />
              <div className="p-4">
                <p className="font-display text-sm font-bold text-slate-900">{product.title}</p>
                <p className="mt-1 text-[11px] text-slate-500">{product.brand || product.category} {product.barcode && `· ${product.barcode}`}</p>
                <div className="mt-4 flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800">{money(product.price)}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] ${product.status === "inactive" ? "bg-slate-100 text-slate-600" : product.stock_count < 5 ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>{product.status === "inactive" ? "Inactive" : `${product.stock_count} in stock`}</span>
                </div>
                <button type="button" disabled={updatingProduct === product.id} onClick={() => void toggleProductStatus(product)} className="mt-4 w-full rounded-lg border border-purple-100 px-3 py-2 text-[11px] font-semibold text-violet-700 transition hover:bg-violet-50 disabled:opacity-50">{updatingProduct === product.id ? "Updating…" : product.status === "inactive" ? "Reactivate listing" : "Deactivate listing"}</button>
              </div>
            </article>
          ))}
          {!inventory.length && <div className="rounded-2xl border border-dashed border-purple-200 bg-white/60 p-8 text-center sm:col-span-2 xl:col-span-3"><Package className="mx-auto h-7 w-7 text-violet-500" /><p className="mt-3 text-sm font-semibold text-slate-800">Your catalog is ready for its first product</p><Link href="/seller/inventory" className="mt-3 inline-block rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white">Add a listing</Link></div>}
        </section>
      )}
      {section === "orders" && <SellerEscrowOrders />}
      {section === "fulfillment" && (
        <section className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-violet-600" /><h2 className="font-display text-sm font-bold text-slate-900">Dispatch pipeline</h2></div>
          <SellerEscrowOrders />
          <p className="mt-3 text-[11px] text-slate-500">Dispatch is enabled only when escrow has been released. Buyers confirm delivery through their order view.</p>
        </section>
      )}
      {section === "astra-check" && (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            ["Overall seller trust", stats?.trust_score],
            ["Compliance", stats?.compliance_score],
            ["Authenticity", stats?.authenticity_score],
            ["Price fairness", stats?.price_fairness_score],
          ].map(([title, score]) => (
            <article key={String(title)} className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm">
              <ShieldCheck className="h-5 w-5 text-violet-600" /><p className="mt-4 text-xs text-slate-500">{title}</p>
              <p className="mt-1 font-display text-2xl font-bold text-slate-900">{typeof score === "number" ? `${Math.round(score)}%` : "Awaiting checks"}</p>
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">Catalog barcode matches identify product references; they do not independently verify seller stock authenticity.</p>
            </article>
          ))}
        </section>
      )}
      {section === "sales-goals" && (
        <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
          <form onSubmit={(event) => void submitGoal(event)} className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm">
            <div className="flex items-center gap-2"><Target className="h-4 w-4 text-violet-600" /><h2 className="font-display text-sm font-bold text-slate-900">Create a sales target</h2></div>
            <label className="mt-4 block text-[11px] font-medium text-slate-600">Goal title<input required minLength={2} value={goalName} onChange={(event) => setGoalName(event.target.value)} className="mt-1.5 w-full rounded-xl border border-purple-100 bg-white px-3 py-2.5 text-xs text-slate-900" placeholder="e.g. October revenue target" /></label>
            <label className="mt-3 block text-[11px] font-medium text-slate-600">Target amount (PKR)<input required type="number" min="1" value={goalTarget} onChange={(event) => setGoalTarget(event.target.value)} className="mt-1.5 w-full rounded-xl border border-purple-100 bg-white px-3 py-2.5 text-xs text-slate-900" /></label>
            <button disabled={savingGoal} className="mt-4 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60">{savingGoal ? "Saving…" : "Save sales goal"}</button>
          </form>
          <div className="flex flex-col gap-3">
            {goals.map((goal) => <article key={goal.id} className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm"><div className="flex justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-900">{goal.title}</h3><p className="mt-1 text-[11px] text-slate-500">{money(goal.current_amount)} of {money(goal.target_amount)}</p></div><span className="text-xs font-bold text-violet-700">{goal.progress_percent}%</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-violet-50"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500" style={{ width: `${Math.min(100, goal.progress_percent)}%` }} /></div></article>)}
            {!goals.length && <p className="rounded-2xl border border-dashed border-purple-200 bg-white/60 p-8 text-center text-xs text-slate-500">Create a goal to start tracking progress. Revenue progress is based on tracked contributions.</p>}
          </div>
        </div>
      )}
      {section === "wallet" && wallet && (
        <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
          <article className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm">
            <CircleDollarSign className="h-5 w-5 text-violet-600" /><p className="mt-4 text-xs text-slate-500">Tracked order revenue</p>
            <p className="mt-1 font-display text-2xl font-bold text-slate-900">{money(wallet.earned_revenue)}</p>
            <p className="mt-3 rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800">Seller payouts are not enabled yet. No payout or wallet balance is presented as withdrawable until a verified settlement provider is configured.</p>
          </article>
          <article className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm"><h2 className="font-display text-sm font-bold text-slate-900">Earnings ledger</h2><p className="mt-1 text-[11px] text-slate-500">Settled order revenue tracked by order status.</p><div className="mt-4 rounded-xl border border-dashed border-purple-200 p-6 text-center text-xs text-slate-500">No seller settlement ledger is connected.</div></article>
        </div>
      )}
      {section === "notifications" && (
        <section className="flex flex-col gap-3">
          {notifications.map((notification) => <article key={notification.id} className="rounded-2xl border border-purple-100/70 bg-white/75 p-4 shadow-sm"><div className="flex items-start gap-3"><span className={`mt-1 h-2 w-2 rounded-full ${notification.is_read ? "bg-slate-300" : "bg-violet-500"}`} /><div><p className="text-xs font-semibold text-slate-900">{notification.title}</p><p className="mt-1 text-xs text-slate-600">{notification.message}</p><p className="mt-2 text-[10px] text-slate-400">{new Date(notification.created_at).toLocaleString()}</p></div></div></article>)}
          {!notifications.length && <p className="rounded-2xl border border-dashed border-purple-200 bg-white/60 p-8 text-center text-xs text-slate-500">You’re all caught up. New seller alerts will appear here.</p>}
        </section>
      )}
      {section === "messages" && <DirectMessagesPanel />}
      {section === "wallet" && !wallet && <div className="rounded-2xl border border-purple-100 bg-white/75 p-6 text-xs text-slate-500">Loading seller earnings…</div>}
      <Link href="/seller/dashboard" className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-700"><TrendingUp className="h-3.5 w-3.5" /> Back to seller overview</Link>
    </PageShell>
  );
}

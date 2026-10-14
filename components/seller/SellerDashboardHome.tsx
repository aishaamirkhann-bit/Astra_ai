"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, BadgeCheck, Box, PackageCheck, Plus, ShieldCheck, Sparkles, Store, TrendingUp } from "lucide-react";
import { getSellerDashboardStats, type SellerDashboardStats } from "@/lib/api";
import SellerInventoryForm from "@/components/seller/SellerInventoryForm";

const money = (value: number) => `Rs. ${Math.round(value).toLocaleString("en-PK")}`;

export default function SellerDashboardHome() {
  const [stats, setStats] = useState<SellerDashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void getSellerDashboardStats().then((data) => {
      if (active) setStats(data);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not load seller analytics.");
    });
    return () => { active = false; };
  }, []);

  const metrics = [
    { label: "Total Revenue", value: stats ? money(stats.total_revenue) : "—", detail: "Settled seller orders", icon: TrendingUp },
    { label: "Pending Orders", value: stats ? String(stats.pending_orders) : "—", detail: "Awaiting action", icon: PackageCheck },
    { label: "Inventory Value", value: stats ? money(stats.inventory_value) : "—", detail: `${stats?.total_products ?? 0} active listings`, icon: Box },
    { label: "Avg. Rating", value: stats ? (stats.average_rating ? `${stats.average_rating.toFixed(1)} / 5` : "New") : "—", detail: "Across reviewed listings", icon: Sparkles },
  ];
  const maxRevenue = Math.max(...(stats?.revenue_series.map((point) => point.amount) ?? [0]), 1);

  return (
    <div className="flex flex-col gap-6">
      <section className="relative overflow-hidden rounded-3xl border border-purple-100/70 bg-gradient-to-br from-white via-violet-50/90 to-indigo-100/70 p-6 shadow-sm sm:p-8">
        <div className="pointer-events-none absolute -right-12 -top-24 h-64 w-64 rounded-full bg-violet-300/35 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-1/3 h-36 w-36 rounded-full bg-indigo-300/25 blur-3xl" />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-white/70 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-violet-700">
              <Store className="h-3.5 w-3.5" /> Seller workspace
            </span>
            <h2 className="mt-4 font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">Manage Smarter, Sell Safer.</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">Your complete command center for inventory, orders, buyer messages, and trusted growth.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/seller/inventory" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-3 text-xs font-semibold text-white shadow-md shadow-violet-500/20 transition hover:-translate-y-0.5 hover:shadow-lg">
              <Plus className="h-4 w-4" /> Add New Listing
            </Link>
            <Link href="/seller/astra-check" className="inline-flex items-center gap-2 rounded-xl border border-purple-200 bg-white/75 px-4 py-3 text-xs font-semibold text-violet-800 transition hover:bg-white">
              <ShieldCheck className="h-4 w-4" /> View Seller Rules
            </Link>
          </div>
        </div>
      </section>

      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">{error}</p>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, detail, icon: Icon }) => (
          <article key={label} className="rounded-2xl border border-purple-100/70 bg-white/75 p-4 shadow-sm backdrop-blur-md transition hover:-translate-y-0.5 hover:shadow-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">{label}</span>
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700"><Icon className="h-4 w-4" /></span>
            </div>
            <p className="mt-3 font-display text-2xl font-bold text-slate-900">{value}</p>
            <p className="mt-1 text-[10px] text-slate-500">{detail}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <article className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm backdrop-blur-md">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-display text-sm font-bold text-slate-900">Seller Trust &amp; Verification</h3>
              <p className="mt-1 text-[11px] text-slate-500">Trust checks across your seller profile and product catalog.</p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[9px] font-bold tracking-wide text-emerald-700">
              <BadgeCheck className="h-3.5 w-3.5" /> OVERALL HEALTH: {stats?.trust_score == null ? "SETUP IN PROGRESS" : stats.trust_score >= 70 ? "HIGHLY TRUSTED" : "ACTION RECOMMENDED"}
            </span>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ["Compliance", stats?.compliance_score],
              ["Authenticity", stats?.authenticity_score],
              ["Price Fairness", stats?.price_fairness_score],
            ].map(([label, score]) => (
              <div key={String(label)} className="rounded-xl border border-purple-100 bg-violet-50/50 p-3">
                <div className="flex justify-between text-[11px] text-slate-600"><span>{label}</span><b className="text-slate-900">{typeof score === "number" ? `${Math.round(score)}%` : "Awaiting"}</b></div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500" style={{ width: `${Math.max(0, Math.min(100, typeof score === "number" ? score : 0))}%` }} /></div>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm backdrop-blur-md">
          <div className="flex items-center justify-between">
            <div><h3 className="font-display text-sm font-bold text-slate-900">Revenue Growth</h3><p className="mt-1 text-[11px] text-slate-500">Recent monthly trend</p></div>
            <TrendingUp className="h-4 w-4 text-violet-600" />
          </div>
          <div className="mt-5 flex h-28 items-end gap-2">
            {(stats?.revenue_series ?? []).map((point) => (
              <div key={point.label} className="flex h-full flex-1 flex-col justify-end gap-1">
                <div title={money(point.amount)} className="min-h-1 rounded-t-md bg-gradient-to-t from-violet-600 to-indigo-400 transition-all" style={{ height: `${Math.max(5, point.amount / maxRevenue * 100)}%` }} />
                <span className="text-center text-[9px] text-slate-500">{point.label}</span>
              </div>
            ))}
            {!stats && <p className="m-auto text-xs text-slate-400">Loading analytics…</p>}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <article className="overflow-hidden rounded-2xl border border-purple-100/70 bg-white/75 shadow-sm backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-purple-100 px-5 py-4">
            <div><h3 className="font-display text-sm font-bold text-slate-900">Top Selling Products</h3><p className="mt-1 text-[11px] text-slate-500">Catalog leaders and inventory status</p></div>
            <Link href="/seller/products" className="inline-flex items-center gap-1 text-[11px] font-semibold text-violet-700 hover:text-violet-900">All products <ArrowUpRight className="h-3.5 w-3.5" /></Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[470px] text-left text-xs">
              <thead className="bg-violet-50/70 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Product</th><th className="px-3 py-3">Price</th><th className="px-3 py-3">Stock</th><th className="px-3 py-3">Sales velocity</th></tr></thead>
              <tbody>
                {stats?.top_products.map((product) => (
                  <tr key={product.id} className="border-t border-purple-50">
                    <td className="px-5 py-3 font-medium text-slate-800">{product.title}</td><td className="px-3 py-3 text-slate-600">{money(product.price)}</td>
                    <td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-[9px] font-semibold ${product.stock_count < 5 ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>{product.stock_count} units</span></td>
                    <td className="px-3 py-3 text-slate-600">{product.sales_velocity} views</td>
                  </tr>
                ))}
                {stats && !stats.top_products.length && <tr><td colSpan={4} className="px-5 py-8 text-center text-slate-500">Add your first product to see catalog performance.</td></tr>}
                {!stats && <tr><td colSpan={4} className="px-5 py-8 text-center text-slate-500">Loading products…</td></tr>}
              </tbody>
            </table>
          </div>
        </article>
        <article className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm backdrop-blur-md">
          <div className="flex items-center gap-2"><div className="grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-violet-700"><PackageCheck className="h-4 w-4" /></div><div><h3 className="font-display text-sm font-bold text-slate-900">Seller tools</h3><p className="text-[10px] text-slate-500">Shortcuts for your daily workflow</p></div></div>
          <div className="mt-4 flex flex-col gap-2">
            {[
              ["/seller/inventory", "Barcode quick-add & stock"],
              ["/seller/orders", "Process buyer orders"],
              ["/seller/fulfillment", "Track fulfillment pipeline"],
              ["/seller/messages", "Reply to buyer inquiries"],
            ].map(([href, label]) => <Link key={href} href={href} className="flex items-center justify-between rounded-xl border border-purple-100 bg-white/70 px-3 py-3 text-xs font-medium text-slate-700 transition hover:border-violet-200 hover:bg-violet-50">{label}<ArrowUpRight className="h-3.5 w-3.5 text-violet-600" /></Link>)}
          </div>
        </article>
      </section>

      <SellerInventoryForm />
    </div>
  );
}

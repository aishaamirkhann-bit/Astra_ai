"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BarChart3, Package, Search, Sparkles } from "lucide-react";
import { getSellerAnalyticsInsights, type SellerAnalyticsInsights } from "@/lib/api";

const money = (value: number | null) => value == null ? "—" : `Rs. ${Math.round(value).toLocaleString("en-PK")}`;
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function SellerInsightsPanel() {
  const [insights, setInsights] = useState<SellerAnalyticsInsights | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void getSellerAnalyticsInsights().then((data) => {
      if (active) setInsights(data);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not load merchant insights.");
    });
    return () => { active = false; };
  }, []);

  return (
    <section aria-labelledby="seller-insights-title" className="rounded-2xl border border-indigo-100 bg-white/80 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-indigo-600" /><h3 id="seller-insights-title" className="font-display text-sm font-bold text-slate-900">Merchant insights</h3></div>
          <p className="mt-1 text-[11px] text-slate-500">Read-only, seller-scoped aggregates from the last {insights?.window_days ?? 30} days.</p>
        </div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[9px] font-semibold text-emerald-700">Aggregated · no buyer identities</span>
      </div>

      {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-xs text-rose-700">{error}</p>}
      {!insights && !error && <p className="mt-4 text-xs text-slate-500">Loading merchant insights…</p>}

      {insights && <>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Negotiations", String(insights.negotiation.session_count)],
            ["Accepted offers", String(insights.negotiation.accepted_offer_count)],
            ["Offer acceptance", percent(insights.negotiation.offer_acceptance_rate)],
            ["Negotiation → paid order", percent(insights.negotiation.negotiation_to_paid_order_rate)],
          ].map(([label, value]) => <article key={label} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3"><p className="text-[10px] text-slate-500">{label}</p><p className="mt-1 text-lg font-bold text-slate-900">{value}</p></article>)}
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <article className="rounded-xl border border-slate-100 p-4">
            <div className="flex items-center gap-2"><Search className="h-4 w-4 text-violet-600" /><h4 className="text-xs font-semibold text-slate-800">Text, voice &amp; visual search trends</h4></div>
            <p className="mt-2 text-xs leading-relaxed text-slate-600">{insights.search_trends.message}</p>
            <p className="mt-2 text-[10px] text-slate-400">No keyword or modality data is inferred from individual buyer activity.</p>
          </article>
          <article className="rounded-xl border border-slate-100 p-4">
            <div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-violet-600" /><h4 className="text-xs font-semibold text-slate-800">Accepted negotiation prices</h4></div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              {[["Low", insights.negotiation.accepted_price_distribution.minimum], ["Median", insights.negotiation.accepted_price_distribution.median], ["High", insights.negotiation.accepted_price_distribution.maximum]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-violet-50/70 p-2"><p className="text-[9px] text-slate-500">{label}</p><p className="mt-1 text-xs font-semibold text-slate-800">{money(typeof value === "number" ? value : null)}</p></div>)}
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{insights.negotiation.pricing_signal}</p>
          </article>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <article className="rounded-xl border border-slate-100 p-4">
            <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-violet-600" /><h4 className="text-xs font-semibold text-slate-800">Negotiated variant demand</h4></div>
            {insights.variant_demand_30d.length ? <ul className="mt-3 space-y-2">{insights.variant_demand_30d.map((trend) => <li key={`${trend.product_id}:${trend.color}:${trend.size}`} className="flex justify-between gap-3 text-[11px]"><span className="truncate text-slate-600">{trend.product_title} · {[trend.color, trend.size].filter(Boolean).join(" / ") || "unspecified variant"}</span><b className="shrink-0 text-slate-800">{trend.negotiations_30d}</b></li>)}</ul> : <p className="mt-2 text-xs text-slate-500">No variant negotiations recorded in this window.</p>}
            <p className="mt-2 text-[10px] text-slate-400">Counts describe negotiation sessions, not search filters.</p>
          </article>
          <article className="rounded-xl border border-slate-100 p-4">
            <div className="flex items-center gap-2"><Package className="h-4 w-4 text-violet-600" /><h4 className="text-xs font-semibold text-slate-800">Inventory health &amp; stock alerts</h4></div>
            <p className="mt-1 text-[10px] text-slate-500">{insights.inventory.active} active listings · {insights.inventory.low_stock} low stock · {insights.inventory.out_of_stock} out of stock</p>
            {insights.inventory.stock_alerts.length ? <ul className="mt-3 space-y-2">{insights.inventory.stock_alerts.map((alert) => <li key={alert.product_id} className="flex gap-2 rounded-lg bg-amber-50/70 p-2.5"><AlertTriangle className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${alert.urgency === "high" ? "text-rose-600" : "text-amber-600"}`} /><div><p className="text-[11px] font-semibold text-slate-800">{alert.product_title} · {alert.stock_count} remaining</p><p className="mt-0.5 text-[10px] text-slate-600">{alert.recommendation}</p></div></li>)}</ul> : <p className="mt-2 text-xs text-slate-500">No active listings are below the {insights.inventory.low_stock_threshold}-unit alert threshold.</p>}
          </article>
        </div>
      </>}
    </section>
  );
}

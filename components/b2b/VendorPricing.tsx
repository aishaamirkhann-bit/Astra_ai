"use client";

import { useEffect, useState } from "react";
import { Check, LoaderCircle, Sparkles } from "lucide-react";
import { getMyVendorSubscription, getVendorPlans, selectVendorPlan, type VendorPlan } from "@/lib/api";

const money = (value: number) => value === 0 ? "Free" : `Rs. ${value.toLocaleString("en-PK")}`;

export default function VendorPricing() {
  const [plans, setPlans] = useState<VendorPlan[]>([]);
  const [current, setCurrent] = useState<{ tier: string; monthly_price: number; status: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void Promise.all([getVendorPlans(), getMyVendorSubscription()]).then(([available, selected]) => {
      if (active) { setPlans(available); setCurrent(selected); }
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Pricing is unavailable."); });
    return () => { active = false; };
  }, []);

  async function choose(tier: VendorPlan["tier"]) {
    setBusy(tier); setError(""); setNotice("");
    try { const result = await selectVendorPlan(tier); setCurrent(result); setNotice(result.message); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not select this plan."); }
    finally { setBusy(null); }
  }

  return <div>
    <div className="mx-auto max-w-2xl text-center"><span className="inline-flex items-center gap-1.5 rounded-full bg-violet-400/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-violet-200"><Sparkles className="h-3 w-3" /> Vendor growth plans</span><h2 className="mt-3 font-display text-2xl font-bold text-white">Choose a plan that fits your distribution business</h2><p className="mt-2 text-xs leading-relaxed text-ink-400">Transparent monthly pricing in PKR. Paid tiers remain pending until billing is completed and confirmed.</p></div>
    {error && <p role="alert" className="mx-auto mt-5 max-w-2xl rounded-xl border border-rose-400/20 bg-rose-400/5 p-3 text-xs text-rose-300">{error}</p>}{notice && <p role="status" className="mx-auto mt-5 max-w-2xl rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-3 text-xs text-emerald-300">{notice}</p>}
    {current && <p className="mt-5 text-center text-[10px] text-ink-500">Current selection: <strong className="text-ink-200">{current.tier}</strong> · {current.status.replace("_", " ")}</p>}
    <div className="mt-7 grid gap-4 lg:grid-cols-3">{plans.map((plan) => <article key={plan.tier} className={`relative rounded-2xl border bg-base-900/70 p-5 ${plan.tier === "Pro" ? "border-violet-300/50 shadow-[0_0_36px_rgba(139,92,246,0.13)]" : "border-base-700"}`}>
      {plan.tier === "Pro" && <span className="absolute -top-2.5 right-4 rounded-full bg-violet-500 px-3 py-1 text-[9px] font-bold text-white">POPULAR</span>}
      <h3 className="font-display text-lg font-bold text-ink-100">{plan.tier}</h3><p className="mt-3 text-2xl font-bold text-white">{money(plan.monthly_price)}<span className="text-[10px] font-normal text-ink-500"> / month</span></p>
      <ul className="mt-5 space-y-3">{plan.features.map((feature) => <li key={feature} className="flex gap-2 text-xs text-ink-300"><Check className="h-4 w-4 shrink-0 text-emerald-300" />{feature}</li>)}</ul>
      <button type="button" onClick={() => void choose(plan.tier)} disabled={busy !== null || (current?.tier === plan.tier && current.status === "active")} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-astra-gradient px-4 py-3 text-xs font-bold text-white disabled:opacity-50">{busy === plan.tier && <LoaderCircle className="h-3.5 w-3.5 animate-spin" />}{current?.tier === plan.tier && current.status === "active" ? "Current plan" : busy === plan.tier ? "Saving…" : plan.tier === "Basic" ? "Select Basic" : "Select plan"}</button>
    </article>)}</div>
    <p className="mt-5 text-center text-[10px] text-ink-600">Plan selection does not charge a payment method. A billing confirmation is required before paid features activate.</p>
  </div>;
}

"use client";

import { useEffect, useState } from "react";
import { getSellerOrderRisk, recordSellerRiskReview, triggerSellerOrderConfirmation, type CodRiskResult } from "@/lib/api";

type OrderRow = { order_ref: string; product_name: string; total: number; order_status: string };
const tone = { LOW: "bg-emerald-100 text-emerald-800", MEDIUM: "bg-amber-100 text-amber-800", HIGH: "bg-rose-100 text-rose-800" };

export default function CodRiskPanel() {
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [risks, setRisks] = useState<Record<string, CodRiskResult>>({});
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    void fetch(`${(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "")}/api/v1/seller/orders`, { credentials: "include", cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error("Seller orders unavailable"); return response.json() as Promise<OrderRow[]>; })
      .then(async (rows) => {
        if (!active) return;
        setOrders(rows);
        const pairs = await Promise.all(rows.map(async (row) => {
          try { return [row.order_ref, await getSellerOrderRisk(row.order_ref)] as const; } catch { return null; }
        }));
        if (active) setRisks(Object.fromEntries(pairs.filter((pair): pair is NonNullable<typeof pair> => pair !== null)));
      }).catch(() => { if (active) setMessage("COD risk screening is unavailable."); });
    return () => { active = false; };
  }, []);
  return <section className="rounded-2xl border border-purple-100/70 bg-white/75 p-5 shadow-sm">
    <h3 className="font-display text-sm font-bold text-slate-900">COD risk review</h3>
    <p className="mt-1 text-[11px] text-slate-500">Advisory estimates only. Payment method is not recorded on orders yet; verify COD status before acting.</p>
    {message && <p role="status" className="mt-3 text-xs text-rose-700">{message}</p>}
    <ul className="mt-3 space-y-3">{orders.map((order) => {
      const risk = risks[order.order_ref];
      return <li key={order.order_ref} className="rounded-xl border border-slate-100 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold text-slate-800">{order.product_name} · {order.order_ref}</p><p className="mt-1 text-[10px] text-slate-500">PKR {Math.round(order.total).toLocaleString("en-PK")} · {order.order_status}</p></div>
          {risk && <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${tone[risk.level]}`}>{risk.level} · {risk.score}%</span>}</div>
        {risk && <><p className="mt-2 text-[10px] text-slate-600">{risk.factors.join(" · ")}</p>{risk.level === "HIGH" && <div className="mt-2 flex flex-wrap gap-2"><button type="button" onClick={() => void triggerSellerOrderConfirmation(order.order_ref).then((result) => setMessage(result.prompt)).catch(() => setMessage("Could not prepare a confirmation request."))} className="rounded-lg bg-violet-700 px-3 py-2 text-[10px] font-semibold text-white">Prepare voice confirmation prompt</button><button type="button" onClick={() => void recordSellerRiskReview(order.order_ref, "Reviewed by seller").then(() => setMessage(`${order.order_ref} marked reviewed; order state unchanged.`)).catch(() => setMessage("Could not record seller review."))} className="rounded-lg border border-slate-300 px-3 py-2 text-[10px] font-semibold text-slate-700">Manual review</button></div>}</>}
      </li>;
    })}</ul>
  </section>;
}

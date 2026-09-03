"use client";
import { useEffect, useState } from "react";
import { dispatchSellerOrder, getSellerOrders, type SellerEscrowOrder } from "@/lib/api";
import { Radio, Send } from "lucide-react";

export default function SellerEscrowOrders() {
  const [orders,setOrders]=useState<SellerEscrowOrder[]>([]); const [error,setError]=useState("");
  const load=()=>getSellerOrders().then(setOrders).catch(e=>setError(e.message));
  useEffect(()=>{ void load(); const timer=setInterval(load,5000); return()=>clearInterval(timer); },[]);
  async function dispatch(ref:string){try{await dispatchSellerOrder(ref);load();}catch(e){setError((e as Error).message)}}
  return <section className="glass rounded-xl2 p-5"><div className="flex items-center justify-between"><h2 className="font-display text-base font-bold text-ink-100">Live Escrow Orders</h2><span className="flex items-center gap-1 text-[10px] text-emerald-400"><Radio className="h-3 w-3 animate-pulse"/>Live · 5s</span></div>{error&&<p className="mt-3 text-xs text-rose-400">{error}</p>}<div className="mt-4 grid gap-3">{orders.length===0&&<p className="text-xs text-ink-500">No buyer orders yet.</p>}{orders.map(order=><article key={order.order_ref} className="grid gap-3 rounded-xl border border-base-600 p-4 sm:grid-cols-[1fr_auto_auto]"><div><p className="text-xs font-bold text-ink-100">{order.product_name}</p><p className="mt-1 text-[10px] text-ink-500">{order.order_ref} · Qty {order.quantity} · Rs. {order.total.toLocaleString()}</p></div><div><p className="text-[9px] uppercase text-ink-500">Escrow</p><p className={order.escrow_status==="LOCKED"?"text-amber-400":order.escrow_status==="REFUNDED"?"text-rose-400":"text-emerald-400"}>{order.escrow_status}</p></div><button disabled={order.order_status==="shipped"||order.escrow_status!=="LOCKED"} onClick={()=>void dispatch(order.order_ref)} className="flex items-center justify-center gap-2 rounded-lg border border-astra-cyan/30 px-3 py-2 text-xs text-astra-cyan disabled:opacity-40"><Send className="h-3.5 w-3.5"/>Dispatch</button></article>)}</div></section>;
}

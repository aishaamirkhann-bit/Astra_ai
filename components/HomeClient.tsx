"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import HeroBanner from "@/components/HeroBanner";
import AstraCheckWidget from "@/components/AstraCheckWidget";
import AiAssistantWidget from "@/components/AiAssistantWidget";
import HumanApprovalWidget from "@/components/HumanApprovalWidget";
import ProductGrid from "@/components/ProductGrid";
import PipelineBar from "@/components/PipelineBar";
import GoalsWalletRail from "@/components/GoalsWalletRail";
import { getDealsWebSocketUrl, getOrdersWebSocketUrl, getWalletWebSocketUrl } from "@/lib/api";
import type { HomePageOut } from "@/lib/types";

export default function HomeClient({ data }: { data: HomePageOut }) {
  const router = useRouter(); const refreshTimer = useRef<number | null>(null);
  useEffect(() => {
    let stopped = false; const sockets: WebSocket[] = []; const retries: number[] = [];
    const refresh = () => { if (refreshTimer.current) clearTimeout(refreshTimer.current); refreshTimer.current = window.setTimeout(() => router.refresh(), 180); };
    const connect = (url: string) => { if (stopped) return; const socket = new WebSocket(url); sockets.push(socket); socket.onmessage = (message) => { try { const event = JSON.parse(message.data) as { type?: string }; if (!["connected", "pong"].includes(event.type ?? "")) refresh(); } catch {} }; socket.onclose = (event) => { if (!stopped && event.code !== 1008) retries.push(window.setTimeout(() => connect(url), 3000)); }; };
    connect(getDealsWebSocketUrl()); connect(getWalletWebSocketUrl(data.user.id)); connect(getOrdersWebSocketUrl());
    const ping = window.setInterval(() => sockets.forEach((socket) => socket.readyState === WebSocket.OPEN && socket.send("ping")), 20000);
    return () => { stopped = true; clearInterval(ping); retries.forEach(clearTimeout); sockets.forEach((socket) => socket.close()); if (refreshTimer.current) clearTimeout(refreshTimer.current); };
  }, [data.user.id, router]);
  return <div className="mx-auto flex max-w-[1600px]"><Sidebar active="Home" /><div className="min-w-0 flex-1"><TopBar unreadNotifications={data.unread_notifications} user={data.user} /><main className="grid grid-cols-1 gap-5 p-4 lg:grid-cols-[1fr_320px] lg:p-8"><div className="flex flex-col gap-5"><div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_260px]"><HeroBanner suggestions={data.hero_suggestions} />{data.astra_check ? <AstraCheckWidget astraCheck={data.astra_check} /> : <EmptyCard title="ASTRA Check waiting" text="Add products to the catalog to start affordability and trust analysis." />}</div><ProductGrid products={data.recommended_products} /><PipelineBar pipeline={data.pipeline} /></div><div className="flex flex-col gap-5">{data.ai_assistant ? <AiAssistantWidget suggestion={data.ai_assistant} /> : <EmptyCard title="AI Assistant ready" text="Recommendations will appear when verified products are available." />}<HumanApprovalWidget approval={data.approval} /><GoalsWalletRail data={data.goals_wallet} /></div></main></div></div>;
}

function EmptyCard({ title, text }: { title: string; text: string }) { return <section className="glass rounded-xl2 p-5"><h2 className="font-display text-sm font-semibold text-ink-100">{title}</h2><p className="mt-2 text-xs leading-5 text-ink-500">{text}</p></section>; }

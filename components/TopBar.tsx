"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Camera, ChevronDown, Mic, Search, User } from "lucide-react";
import MobileNav from "@/components/MobileNav";
import ThemeToggle from "@/components/ThemeToggle";
import { clearSession } from "@/lib/auth";
import { getCurrentUser, logoutUser } from "@/lib/api";
import type { LoginResponse } from "@/lib/types";

const LANGUAGES = ["English", "Urdu", "Roman Urdu"] as const;
const COPY = { English: ["Search products, brands, or categories", "Search in English"], Urdu: ["مصنوعات، برانڈز یا کیٹیگریز تلاش کریں", "اردو میں تلاش کریں"], "Roman Urdu": ["Product, brand ya category search karein", "Roman Urdu mein search karein"] } as const;
const PROFILE_LINKS = [["My Account", "/account"], ["Wallet & Ledger", "/wallet"], ["Orders & Receipts", "/orders"]] as const;
type Recognition = { lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void; onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null };

export default function TopBar({ unreadNotifications = 0, user }: { unreadNotifications?: number; user?: LoginResponse["user"] }) {
  const router = useRouter();
  const pathname = usePathname();
  const recognition = useRef<Recognition | null>(null);
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]>("Roman Urdu");
  const [query, setQuery] = useState("");
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [profileUser, setProfileUser] = useState(user);

  useEffect(() => { try { setHistory(JSON.parse(localStorage.getItem("astra-search-history") ?? "[]")); } catch { setHistory([]); } }, []);
  useEffect(() => { if (user) setProfileUser(user); else void getCurrentUser().then(setProfileUser).catch(() => router.replace("/login")); }, [router, user]);
  useEffect(() => { const handler = (event: Event) => { const detail = (event as CustomEvent<{ query: string; commit?: boolean }>).detail; setQuery(detail.query); if (detail.commit && pathname !== "/explore") router.push(`/explore?q=${encodeURIComponent(detail.query)}`); }; addEventListener("astra:search", handler); return () => removeEventListener("astra:search", handler); }, [pathname, router]);

  function search(value: string) {
    const clean = value.trim(); if (!clean) return;
    const next = [clean, ...history.filter((item) => item.toLowerCase() !== clean.toLowerCase())].slice(0, 5);
    setHistory(next); localStorage.setItem("astra-search-history", JSON.stringify(next));
    if (pathname === "/explore") dispatchEvent(new CustomEvent("astra:search", { detail: { query: clean, commit: true } })); else router.push(`/explore?q=${encodeURIComponent(clean)}`);
    setHistoryOpen(false);
  }
  function voice() {
    if (listening) { recognition.current?.stop(); return; }
    const speechWindow = window as Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) { setStatus("Use Chrome or Edge for voice search"); return; }
    const engine = new Constructor(); engine.lang = language === "Urdu" ? "ur-PK" : "en-US"; engine.interimResults = false; engine.continuous = false;
    engine.onresult = (event) => { const text = event.results[0][0].transcript; setQuery(text); search(text); };
    engine.onend = () => { setListening(false); recognition.current = null; }; engine.onerror = () => { setListening(false); setStatus("Voice search could not hear that. Try again."); };
    recognition.current = engine; setListening(true); setStatus("Listening…"); try { engine.start(); } catch { setListening(false); setStatus("Microphone is busy. Try again."); }
  }
  function image(file: File) {
    setStatus(`Preparing ${file.name}…`);
    if (pathname === "/explore") { dispatchEvent(new CustomEvent("astra:file-search", { detail: { file, queryType: "image" } })); dispatchEvent(new CustomEvent("astra:search-context", { detail: { mode: "image", label: file.name, previewUrl: URL.createObjectURL(file) } })); return; }
    const reader = new FileReader(); reader.onload = () => { sessionStorage.setItem("astra:image-search", JSON.stringify({ name: file.name, type: file.type, data: reader.result })); router.push(`/explore?image_search=true&image_name=${encodeURIComponent(file.name)}`); }; reader.readAsDataURL(file);
  }
  async function logout() { await logoutUser().catch(() => undefined); clearSession(); router.replace("/login"); router.refresh(); }

  return <header className="flex flex-col gap-3 border-b border-base-600/60 px-4 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-8">
    <div className="flex min-w-0 flex-1 items-center gap-3"><MobileNav /><div className="glass glass-hover flex min-w-0 flex-1 items-center gap-3 rounded-full px-4 py-2.5"><Search className="h-4 w-4 shrink-0 text-ink-500" /><div className="relative min-w-0 flex-1"><input value={query} onFocus={() => setHistoryOpen(true)} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && search(query)} placeholder={COPY[language][0]} aria-label={COPY[language][1]} className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none" />{historyOpen && history.length > 0 && <div className="absolute left-0 right-0 top-10 z-40 rounded-xl border border-base-600 bg-base-900 p-2 shadow-card">{history.map((item) => <button key={item} onClick={() => search(item)} className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs text-ink-300 hover:bg-base-800">{item}</button>)}</div>}</div>{status && <span className="hidden max-w-32 truncate text-[10px] text-signal-hold sm:block">{status}</span>}<button onClick={voice} className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${listening ? "animate-pulse bg-astra-gradient text-white" : "bg-base-700 text-ink-300"}`} aria-label="Voice search"><Mic className="h-4 w-4" /></button><label className="grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-full bg-base-700 text-ink-300" aria-label="Image search"><Camera className="h-4 w-4" /><input type="file" accept="image/*" className="hidden" onChange={(event) => event.target.files?.[0] && image(event.target.files[0])} /></label></div><div className="hidden gap-1 xl:flex">{LANGUAGES.map((item) => <button key={item} onClick={() => setLanguage(item)} className={`rounded-full px-3 py-1.5 text-xs ${language === item ? "bg-astra-gradient-soft text-ink-100" : "text-ink-500"}`}>{item}</button>)}</div></div>
    <div className="flex items-center justify-between gap-3 lg:justify-end"><ThemeToggle /><Link href="/notifications" className="relative grid h-9 w-9 place-items-center rounded-full bg-base-800 text-ink-300" aria-label="Notifications"><Bell className="h-4 w-4" />{unreadNotifications > 0 && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-reject" />}</Link><div className="relative"><button onClick={() => setProfileOpen((value) => !value)} className="flex items-center gap-2 rounded-full bg-base-800 py-1 pl-1 pr-2.5 text-ink-100"><span className="grid h-7 w-7 place-items-center rounded-full bg-astra-gradient text-[10px] font-bold text-white">{profileUser?.name?.[0]?.toUpperCase() ?? <User className="h-3.5 w-3.5" />}</span><span className="hidden text-xs font-medium md:inline">{profileUser?.name ?? "Account"}</span><ChevronDown className="h-3.5 w-3.5 text-ink-500" /></button>{profileOpen && <div className="absolute right-0 top-11 z-50 w-56 rounded-xl border border-base-600 bg-base-900 p-2 shadow-2xl"><div className="border-b border-base-600 px-3 py-2"><p className="truncate text-xs font-semibold text-ink-100">{profileUser?.name}</p><p className="mt-1 text-[10px] capitalize text-ink-500">{profileUser?.role}</p></div>{PROFILE_LINKS.map(([label, href]) => <Link key={href} href={href} onClick={() => setProfileOpen(false)} className="block rounded-lg px-3 py-2 text-xs text-ink-300 hover:bg-base-800">{label}</Link>)}<button onClick={() => void logout()} className="w-full rounded-lg px-3 py-2 text-left text-xs font-semibold text-rose-400 hover:bg-rose-500/10">Logout</button></div>}</div></div>
  </header>;
}

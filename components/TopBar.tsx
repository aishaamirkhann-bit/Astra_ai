"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Camera, Check, ChevronDown, Loader2, MapPin, Mic, Search, ShoppingBag, Store, User } from "lucide-react";
import MobileNav from "@/components/MobileNav";
import ThemeToggle from "@/components/ThemeToggle";
import { clearSession, storeAccountMode, storeSession, storeUserProfile } from "@/lib/auth";
import { changeAccountRole, getCurrentUser, getVoiceWebSocketUrl, logoutUser, parseVoiceIntent, updateRegionalPreferences } from "@/lib/api";
import { useAccountMode } from "@/lib/useAccountMode";
import { showToast } from "@/lib/toast";
import type { LoginResponse } from "@/lib/types";
import LocationModal from "@/components/auth/LocationLanguageModal";
import { CURRENCY_OPTIONS, getCountry, getSavedCountry, isCountryCode, LANGUAGES_BY_COUNTRY, LANGUAGE_STORAGE_KEY, saveCountry, type CountryCode, type DisplayCurrency, type LanguageName } from "@/lib/region";
import { useRegionalCurrency } from "@/lib/useRegionalCurrency";
import { isARIntent } from "@/lib/arIntent";
import { flushVoiceEvents, interruptVoiceOutput, parseVoiceEvent, sendVoiceTranscript } from "@/lib/voiceStream.mjs";

const COPY = {
  English: ["Search products, brands, or categories", "Search in English"],
  Urdu: ["Ù…ØµÙ†ÙˆØ¹Ø§ØªØŒ Ø¨Ø±Ø§Ù†ÚˆØ² ÛŒØ§ Ú©ÛŒÙ¹ÛŒÚ¯Ø±ÛŒØ² ØªÙ„Ø§Ø´ Ú©Ø±ÛŒÚº", "Ø§Ø±Ø¯Ùˆ Ù…ÛŒÚº ØªÙ„Ø§Ø´ Ú©Ø±ÛŒÚº"],
  "Roman Urdu": ["Product, brand ya category search karein", "Roman Urdu mein search karein"],
  Punjabi: ["Product, brand ya shreni labho", "Punjabi vich search"],
  Pashto: ["Ø¯ Ù…Ø­ØµÙˆÙ„Ø§ØªÙˆ Ø§Ùˆ Ø¨Ø±Ø§Ù†Ú‰ÙˆÙ†Ùˆ Ù„Ù¼ÙˆÙ†", "Ù¾Ù‡ Ù¾ÚšØªÙˆ Ú©Û Ù„Ù¼ÙˆÙ†"],
  Sindhi: ["Ù¾Ø±Ø§ÚŠÚªÙ½ØŒ Ø¨Ø±Ø§Ù†ÚŠ ÙŠØ§ ÚªÙŠÙ½ÙŠÚ¯Ø±ÙŠ Ú³ÙˆÙ„ÙŠÙˆ", "Ø³Ù†ÚŒÙŠ Û¾ Ú³ÙˆÙ„Ø§"],
} as const;
const BUYER_PROFILE_LINKS = [["My Account", "/account"], ["Wallet & Ledger", "/wallet"], ["Orders & Receipts", "/orders"]] as const;
const SELLER_PROFILE_LINKS = [["Seller Dashboard", "/seller/dashboard"], ["Inventory", "/seller/inventory"], ["Orders", "/seller/orders"], ["Seller Wallet", "/seller/wallet"]] as const;
type Recognition = { lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void; onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null };

export default function TopBar({ unreadNotifications = 0, user }: { unreadNotifications?: number; user?: LoginResponse["user"] }) {
  const router = useRouter();
  const pathname = usePathname();
  const { currency, setCurrency } = useRegionalCurrency();
  const accountMode = useAccountMode();
  const profileLinks = accountMode === "seller" ? SELLER_PROFILE_LINKS : BUYER_PROFILE_LINKS;
  const recognition = useRef<Recognition | null>(null);
  const voiceSocket = useRef<WebSocket | null>(null);
  const pendingVoiceEvents = useRef<string[]>([]);
  const voiceRecorder = useRef<MediaRecorder | null>(null);
  const voiceMediaStream = useRef<MediaStream | null>(null);
  const [region, setRegion] = useState<CountryCode | null>(null);
  const [locationOpen, setLocationOpen] = useState(false);
  const [language, setLanguage] = useState<LanguageName>("English");
  const [query, setQuery] = useState("");
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [profileUser, setProfileUser] = useState(user);
  const [switchingRole, setSwitchingRole] = useState<"buyer" | "seller" | null>(null);

  const activeLanguages = LANGUAGES_BY_COUNTRY[region ?? "PK"];
  const countryInfo = region ? getCountry(region) : null;
  const searchCopy = COPY[language as keyof typeof COPY] ?? COPY.English;

  useEffect(() => {
    const storedCountry = getSavedCountry();
    const savedCountry = storedCountry ?? (isCountryCode(user?.country ?? null) ? user!.country as CountryCode : null);
    if (!savedCountry) {
      setLocationOpen(true);
      return;
    }
    if (!storedCountry) {
      saveCountry(savedCountry);
      setCurrency(getCountry(savedCountry).currency as DisplayCurrency);
      // The profile may contain a migration/signup default. Ask once in this
      // browser before treating that region as an acknowledged preference.
      setLocationOpen(true);
    }
    setRegion(savedCountry);
    const savedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY) ?? user?.preferred_language ?? null;
    const available = LANGUAGES_BY_COUNTRY[savedCountry];
    setLanguage(available.some((option) => option.name === savedLanguage) ? savedLanguage as LanguageName : available[0].name as LanguageName);
  }, [user, setCurrency]);
  useEffect(() => { try { setHistory(JSON.parse(localStorage.getItem("astra-search-history") ?? "[]")); } catch { setHistory([]); } }, []);

  function chooseCountry(country: CountryCode, preferredLanguage: LanguageName = language) {
    const available = LANGUAGES_BY_COUNTRY[country];
    const nextLanguage = available.some((option) => option.name === preferredLanguage) ? preferredLanguage : "English";
    setRegion(country);
    setLanguage(nextLanguage);
    saveCountry(country);
    setCurrency(getCountry(country).currency as DisplayCurrency);
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    void updateRegionalPreferences(country, nextLanguage).then((profile) => { setProfileUser(profile); storeUserProfile(profile); }).catch(() => undefined);
    setLocationOpen(false);
  }
  useEffect(() => {
    if (user) {
      setProfileUser(user);
      storeAccountMode(user.role);
    } else {
      void getCurrentUser().then((currentUser) => {
        setProfileUser(currentUser);
        storeUserProfile(currentUser);
      }).catch(() => router.replace("/login"));
    }
  }, [router, user]);
  useEffect(() => { const handler = (event: Event) => { const detail = (event as CustomEvent<{ query: string; commit?: boolean }>).detail; setQuery(detail.query); if (detail.commit && pathname !== "/explore") router.push(`/explore?q=${encodeURIComponent(detail.query)}`); }; addEventListener("astra:search", handler); return () => removeEventListener("astra:search", handler); }, [pathname, router]);
  useEffect(() => () => {
    voiceRecorder.current?.state !== "inactive" && voiceRecorder.current?.stop();
    voiceMediaStream.current?.getTracks().forEach((track) => track.stop());
    voiceSocket.current?.close();
  }, []);

  async function streamMicrophoneAudio(socket: WebSocket) {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (socket.readyState !== WebSocket.OPEN) { stream.getTracks().forEach((track) => track.stop()); return; }
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      voiceMediaStream.current = stream;
      voiceRecorder.current = recorder;
      socket.send(JSON.stringify({ type: "audio_start", mime }));
      recorder.ondataavailable = (event) => { if (event.data.size && socket.readyState === WebSocket.OPEN) socket.send(event.data); };
      recorder.onstop = () => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "audio_end" }));
        stream.getTracks().forEach((track) => track.stop());
        if (voiceRecorder.current === recorder) voiceRecorder.current = null;
        if (voiceMediaStream.current === stream) voiceMediaStream.current = null;
      };
      recorder.start(250);
    } catch {
      setStatus("Live audio unavailable; using browser transcription");
    }
  }

  function search(value: string) {
    const clean = value.trim(); if (!clean) return;
    const next = [clean, ...history.filter((item) => item.toLowerCase() !== clean.toLowerCase())].slice(0, 5);
    setHistory(next); localStorage.setItem("astra-search-history", JSON.stringify(next));
    if (accountMode === "seller") {
      router.push(`/seller/inventory?q=${encodeURIComponent(clean)}`);
      setHistoryOpen(false);
      return;
    }
    if (pathname === "/explore") dispatchEvent(new CustomEvent("astra:search", { detail: { query: clean, commit: true } })); else router.push(`/explore?q=${encodeURIComponent(clean)}`);
    setHistoryOpen(false);
  }
  function voice() {
    if (listening) { recognition.current?.stop(); return; }
    const speechWindow = window as Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
    const Constructor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!Constructor) { setStatus("Use Chrome or Edge for voice search"); return; }
    const engine = new Constructor(); engine.lang = activeLanguages.find((option) => option.name === language)?.locale ?? "en-US"; engine.interimResults = true; engine.continuous = false;
    if (window.speechSynthesis?.speaking) {
      interruptVoiceOutput(voiceSocket.current, window.speechSynthesis);
    }
    voiceSocket.current?.close();
    pendingVoiceEvents.current = [];
    const socket = new WebSocket(getVoiceWebSocketUrl());
    voiceSocket.current = socket;
    socket.onopen = () => {
      flushVoiceEvents(socket, pendingVoiceEvents.current);
      void streamMicrophoneAudio(socket);
    };
    socket.onmessage = (message) => {
      try {
        const event = parseVoiceEvent(message.data) as { type?: string; mode?: string; text?: string; final?: boolean; intent?: { category?: string | null; budget_max?: number | null }; assistant_suggestion?: string | null } | null;
        if (!event) return;
        if (event.type === "transcript" && event.final && event.intent) {
          const bits = [event.intent.category, event.intent.budget_max ? `â‰¤ Rs. ${event.intent.budget_max.toLocaleString()}` : ""].filter(Boolean).join(" Â· ");
          setStatus(event.assistant_suggestion || `Streaming NLU${bits ? ` Â· ${bits}` : ""}`);
        } else if (event.type === "interrupted") setStatus("Voice output interrupted");
      } catch { /* Ignore malformed stream events and keep browser recognition responsive. */ }
    };
    socket.onclose = () => { if (voiceSocket.current === socket) voiceSocket.current = null; };
    engine.onresult = (event) => {
      let interim = "";
      let finalText = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const text = result[0].transcript;
        if ((result as unknown as { isFinal?: boolean }).isFinal) finalText += text;
        else interim += text;
      }
      const text = (finalText || interim).trim();
      if (text) sendVoiceTranscript(socket, pendingVoiceEvents.current, text, Boolean(finalText));
      if (!text || !finalText) return;
      setQuery(text);
      if (isARIntent(text)) {
        if (pathname.startsWith("/product/")) {
          setStatus("Opening read-only AR preview");
          window.dispatchEvent(new CustomEvent("astra:ar-intent"));
        } else {
          setStatus("Open a product page to preview it in AR");
        }
        return;
      }
      const voiceLocale = activeLanguages.find((option) => option.name === language)?.locale ?? "en-US";
      void parseVoiceIntent(text, undefined, voiceLocale, region ?? getSavedCountry() ?? "PK").then((intent) => {
        const bits = [intent.category, intent.budget ? `â‰¤ Rs. ${intent.budget.toLocaleString()}` : ""].filter(Boolean).join(" Â· ");
        setStatus(`ASTRA Intent: Search${bits ? ` Â· ${bits}` : ""}`);
        if (intent.cross_border_advisory?.message) setStatus(intent.cross_border_advisory.message);
        search(text);
      }).catch(() => search(text));
    };
    const stopAudioStream = () => {
      if (voiceRecorder.current?.state === "recording") voiceRecorder.current.stop();
    };
    engine.onend = () => { setListening(false); recognition.current = null; stopAudioStream(); };
    engine.onerror = () => { setListening(false); setStatus("Voice search could not hear that. Try again."); stopAudioStream(); };
    recognition.current = engine; setListening(true); setStatus("Listeningâ€¦"); try { engine.start(); } catch { setListening(false); setStatus("Microphone is busy. Try again."); }
  }
  function image(file: File) {
    if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type) || file.size > 5 * 1024 * 1024) {
      setStatus("Choose a JPEG, PNG, or WebP image up to 5 MB");
      return;
    }
    setStatus(`Preparing ${file.name}â€¦`);
    if (accountMode === "seller") {
      setStatus(`Seller search ready for ${file.name}`);
      return;
    }
    if (pathname === "/explore") { dispatchEvent(new CustomEvent("astra:file-search", { detail: { file, queryType: "image", text: query } })); dispatchEvent(new CustomEvent("astra:search-context", { detail: { mode: "image", label: file.name, previewUrl: URL.createObjectURL(file) } })); return; }
    const reader = new FileReader(); reader.onload = () => { sessionStorage.setItem("astra:image-search", JSON.stringify({ name: file.name, type: file.type, data: reader.result, text: query })); router.push(`/explore?image_search=true&image_name=${encodeURIComponent(file.name)}`); }; reader.readAsDataURL(file);
  }
  async function logout() { await logoutUser().catch(() => undefined); clearSession(); router.replace("/login"); router.refresh(); }
  async function switchAccountMode(role: "buyer" | "seller") {
    if (!profileUser || role === accountMode || switchingRole) return;
    setSwitchingRole(role);
    try {
      const session = await changeAccountRole(role);
      storeSession(session);
      setProfileUser(session.user);
      setProfileOpen(false);
      showToast(`Switched to ${role === "seller" ? "Seller" : "Buyer"} Mode`, "success");
      const destination = role === "seller" ? "/seller/dashboard" : "/buyer/dashboard";
      router.push(destination);
      router.refresh();
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Could not switch account mode.", "error");
    } finally {
      setSwitchingRole(null);
    }
  }

  return (
    <header className={`flex flex-col gap-3 border-b px-4 py-4 transition-colors lg:flex-row lg:items-center lg:justify-between lg:px-8 ${
      accountMode === "seller" ? "border-astra-violet/25" : "border-base-600/60"
    }`}>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <MobileNav />
        <div className="glass glass-hover flex min-w-0 flex-1 items-center gap-3 rounded-full px-4 py-2.5">
          <Search className="h-4 w-4 shrink-0 text-ink-500" />
          <div className="relative min-w-0 flex-1">
            <input
              value={query}
              onFocus={() => setHistoryOpen(true)}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && search(query)}
              placeholder={accountMode === "seller" ? "Search Listings, Orders, Barcodes, or Inventory..." : searchCopy[0]}
              aria-label={accountMode === "seller" ? "Search Listings, Orders, Barcodes, or Inventory" : searchCopy[1]}
              className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
            />
            {historyOpen && history.length > 0 && (
              <div className="absolute left-0 right-0 top-10 z-40 rounded-xl border border-base-600 bg-base-900 p-2 shadow-card">
                {history.map((item) => (
                  <button
                    key={item}
                    onClick={() => search(item)}
                    className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs text-ink-300 hover:bg-base-800"
                  >
                    {item}
                  </button>
                ))}
              </div>
            )}
          </div>
          {status && <span className="hidden max-w-32 truncate text-[10px] text-signal-hold sm:block">{status}</span>}
          {accountMode === "seller" ? (
            <div className="flex shrink-0 items-center gap-1.5">
              <Link href="/seller/orders" className="rounded-full bg-violet-50 px-3 py-2 text-[10px] font-semibold text-violet-700 transition hover:bg-violet-100">Orders</Link>
              <Link href="/seller/inventory" className="rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 px-3 py-2 text-[10px] font-semibold text-white transition hover:opacity-90">Add listing</Link>
            </div>
          ) : (
            <>
              <button
                onClick={voice}
                className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${
                  listening ? "animate-pulse bg-astra-gradient text-white" : "bg-base-700 text-ink-300"
                }`}
                aria-label="Voice search"
              >
                <Mic className="h-4 w-4" />
              </button>
              <label className="grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-full bg-base-700 text-ink-300" aria-label="Image search">
                <Camera className="h-4 w-4" />
                <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(event) => event.target.files?.[0] && image(event.target.files[0])} />
              </label>
            </>
          )}
        </div>
        <button type="button" onClick={() => setLocationOpen(true)} aria-label="Change country or region" className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-base-600 bg-base-800 px-2 py-2 text-[10px] font-semibold text-ink-200 hover:border-astra-cyan/50 sm:px-2.5">
          <MapPin className="h-3.5 w-3.5 text-astra-cyan" />
          <span>{countryInfo?.code ?? "Region"}</span>
          {countryInfo && <span className="hidden text-ink-500 sm:inline">{countryInfo.currency}</span>}
          <ChevronDown className="h-3 w-3 text-ink-500" />
        </button>
        <label className="shrink-0 rounded-xl border border-base-600 bg-base-800 px-2 py-1.5 text-ink-100">
          <span className="sr-only">Display currency</span>
          <select aria-label="Display currency" value={currency} onChange={(event) => setCurrency(event.target.value as DisplayCurrency)} className="max-w-[72px] bg-transparent text-[10px] font-medium outline-none">
            {CURRENCY_OPTIONS.map((option) => <option key={option} value={option} className="bg-base-900">{option}</option>)}
          </select>
        </label>
        <label className="shrink-0 rounded-xl border border-base-600 bg-base-800 px-2 py-1.5 text-ink-100">
          <span className="sr-only">Interface and voice language</span>
          <select
            aria-label="Interface and voice language"
            value={language}
            onChange={(event) => { const next = event.target.value as LanguageName; setLanguage(next); window.localStorage.setItem(LANGUAGE_STORAGE_KEY, next); if (region) void updateRegionalPreferences(region, next).then((profile) => { setProfileUser(profile); storeUserProfile(profile); }).catch(() => undefined); }}
            className="max-w-[150px] bg-transparent text-[11px] font-medium outline-none"
          >
            {activeLanguages.map((item) => <option key={item.name} value={item.name} className="bg-base-900">{item.label}</option>)}
          </select>
        </label>
      </div>
      <div className="flex items-center justify-between gap-3 lg:justify-end">
        {accountMode === "seller" && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-astra-violet/30 bg-astra-gradient-soft px-2.5 py-1 text-[10px] font-semibold text-astra-cyan">
            <Store className="h-3 w-3" /> Seller Mode
          </span>
        )}
        <ThemeToggle />
        <Link href="/notifications" className="relative grid h-9 w-9 place-items-center rounded-full bg-base-800 text-ink-300" aria-label="Notifications">
          <Bell className="h-4 w-4" />
          {unreadNotifications > 0 && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-reject" />}
        </Link>
        <div className="relative">
          <button
            onClick={() => setProfileOpen((value) => !value)}
            aria-expanded={profileOpen}
            aria-haspopup="menu"
            aria-label="Open profile menu"
            className={`flex items-center gap-2 rounded-full border py-1 pl-1 pr-2.5 text-ink-100 transition-colors ${
              accountMode === "seller" ? "border-astra-violet/30 bg-astra-gradient-soft" : "border-transparent bg-base-800"
            }`}
          >
            <span className="grid h-7 w-7 place-items-center rounded-full bg-astra-gradient text-[10px] font-bold text-white">
              {profileUser?.name?.[0]?.toUpperCase() ?? <User className="h-3.5 w-3.5" />}
            </span>
            <span className="hidden text-xs font-medium md:inline">{profileUser?.name ?? "Account"}</span>
            <ChevronDown className="h-3.5 w-3.5 text-ink-500" />
          </button>
          {profileOpen && (
            <div className="absolute right-0 top-11 z-50 w-64 rounded-xl border border-base-600 bg-base-900 p-2 shadow-2xl" role="menu">
              <div className="border-b border-base-600 px-3 py-2">
                <p className="truncate text-xs font-semibold text-ink-100">{profileUser?.name}</p>
                <p className="mt-1 truncate text-[10px] text-ink-500">{profileUser?.email}</p>
              </div>
              {profileUser && (
                <div className="border-b border-base-600 px-3 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-ink-500">Account mode</span>
                    {switchingRole && <Loader2 className="h-3 w-3 animate-spin text-astra-cyan" />}
                  </div>
                  <div role="radiogroup" aria-label="Account mode" className="relative grid grid-cols-2 rounded-lg border border-base-600 bg-base-800 p-1">
                    <span
                      aria-hidden="true"
                      className={`absolute bottom-1 top-1 w-[calc(50%-4px)] rounded-md transition-transform duration-200 ${
                        accountMode === "seller" ? "translate-x-full bg-astra-gradient-soft" : "translate-x-0 bg-astra-gradient-soft"
                      }`}
                    />
                    <button
                      type="button"
                      role="radio"
                      aria-checked={accountMode === "buyer"}
                      aria-label="Switch to Buyer Mode"
                      disabled={!profileUser || switchingRole !== null}
                      onClick={() => void switchAccountMode("buyer")}
                      className={`relative z-10 flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-[11px] font-medium transition-colors disabled:cursor-wait ${
                        accountMode === "buyer" ? "text-ink-100" : "text-ink-500 hover:text-ink-300"
                      }`}
                    >
                      {accountMode === "buyer" ? <Check className="h-3 w-3" /> : <ShoppingBag className="h-3 w-3" />}
                      Buyer
                    </button>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={accountMode === "seller"}
                      aria-label="Switch to Seller Mode"
                      disabled={!profileUser || switchingRole !== null}
                      onClick={() => void switchAccountMode("seller")}
                      className={`relative z-10 flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-[11px] font-medium transition-colors disabled:cursor-wait ${
                        accountMode === "seller" ? "text-astra-cyan" : "text-ink-500 hover:text-ink-300"
                      }`}
                    >
                      {accountMode === "seller" ? <Check className="h-3 w-3" /> : <Store className="h-3 w-3" />}
                      Seller
                    </button>
                  </div>
                </div>
              )}
              {profileLinks.map(([label, href]) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setProfileOpen(false)}
                  className="block rounded-lg px-3 py-2 text-xs text-ink-300 hover:bg-base-800"
                >
                  {label}
                </Link>
              ))}
              <button
                onClick={() => void logout()}
                className="w-full rounded-lg px-3 py-2 text-left text-xs font-semibold text-rose-400 hover:bg-rose-500/10"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
      <LocationModal open={locationOpen} required={!region} selectedCountry={region} selectedLanguage={language} onSelect={chooseCountry} onClose={() => setLocationOpen(false)} />
    </header>
  );
}

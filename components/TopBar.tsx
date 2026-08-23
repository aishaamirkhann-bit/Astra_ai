"use client";

import { useEffect, useRef, useState } from "react";
import { Search, Mic, Camera, Bell, ChevronDown, User } from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import MobileNav from "@/components/MobileNav";

const LANGUAGES = ["English", "Urdu", "Roman Urdu"] as const;
const LANGUAGE_COPY = {
  English: { placeholder: "Search products, brands, or categories", hint: "Search in English" },
  Urdu: { placeholder: "مصنوعات، برانڈز یا کیٹیگریز تلاش کریں", hint: "اردو میں تلاش کریں" },
  "Roman Urdu": { placeholder: "Product, brand ya category search karein", hint: "Roman Urdu mein search karein" },
} as const;

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export default function TopBar() {
  const [lang, setLang] = useState<(typeof LANGUAGES)[number]>("Roman Urdu");
  const [listening, setListening] = useState(false);
  const [imageSelected, setImageSelected] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    const handleSearch = (event: Event) => {
      setQuery((event as CustomEvent<{ query: string }>).detail.query);
    };
    window.addEventListener("astra:search", handleSearch);
    return () => window.removeEventListener("astra:search", handleSearch);
  }, []);

  useEffect(() => {
    const savedHistory = window.localStorage.getItem("astra-search-history");
    if (savedHistory) setHistory(JSON.parse(savedHistory));
  }, []);

  const commitSearch = (value: string) => {
    const trimmedValue = value.trim();
    if (!trimmedValue) return;
    const nextHistory = [trimmedValue, ...history.filter((item) => item.toLowerCase() !== trimmedValue.toLowerCase())].slice(0, 5);
    setHistory(nextHistory);
    window.localStorage.setItem("astra-search-history", JSON.stringify(nextHistory));
    window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: trimmedValue, commit: true } }));
  };

  const selectFile = (file: File, queryType: "image") => {
    if (queryType === "image") setImageSelected(true);
    window.dispatchEvent(new CustomEvent("astra:file-search", { detail: { file, queryType } }));
  };

  const updateQuery = (value: string) => {
    setQuery(value);
    window.dispatchEvent(new CustomEvent("astra:search", { detail: { query: value, commit: false } }));
  };

  const toggleVoiceSearch = async () => {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }
    const speechWindow = window as Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
    const SpeechRecognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceStatus("Use Chrome or Edge for voice search");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = lang === "Urdu" ? "ur-PK" : "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setQuery(transcript);
      setVoiceStatus("");
      commitSearch(transcript);
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onerror = () => {
      setListening(false);
      recognitionRef.current = null;
      setVoiceStatus("Voice search could not hear that. Try again.");
    };
    recognitionRef.current = recognition;
    setVoiceStatus("Listening...");
    setListening(true);
    try {
      recognition.start();
    } catch {
      setListening(false);
      recognitionRef.current = null;
      setVoiceStatus("Microphone is busy. Try again.");
    }
  };

  return (
    <header className="flex flex-col gap-3 border-b border-base-600/60 px-4 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-8">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <MobileNav />
        <div className="glass glass-hover flex min-w-0 flex-1 items-center gap-3 rounded-full px-4 py-2.5">
          <Search className="h-4 w-4 shrink-0 text-ink-500" />
          <div className="relative min-w-0 flex-1">
            <input value={query} onFocus={() => setShowHistory(true)} onChange={(event) => updateQuery(event.target.value)} onKeyDown={(event) => {
              if (event.key === "Enter") commitSearch(query);
            }} placeholder={LANGUAGE_COPY[lang].placeholder} aria-label={LANGUAGE_COPY[lang].hint} className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none" />
            {showHistory && history.length > 0 && (
              <div className="absolute left-0 right-0 top-10 z-30 rounded-xl border border-base-600 bg-base-900 p-2 shadow-card" onMouseLeave={() => setShowHistory(false)}>
                <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-500">Recent searches</p>
                {history.map((item) => <button key={item} type="button" onClick={() => { setQuery(item); commitSearch(item); setShowHistory(false); }} className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs text-ink-300 hover:bg-base-800 hover:text-ink-100">{item}</button>)}
              </div>
            )}
          </div>
          {query && <button type="button" onClick={() => updateQuery("")} aria-label="Clear search" className="shrink-0 text-xs text-ink-500 hover:text-ink-100">Clear</button>}
          {voiceStatus && <span className="hidden max-w-32 truncate text-[10px] text-signal-hold sm:inline" title={voiceStatus}>{voiceStatus}</span>}
          <button type="button" aria-label={listening ? "Stop voice search" : "Start voice search"} aria-pressed={listening} onClick={() => void toggleVoiceSearch()} className={["grid h-8 w-8 shrink-0 place-items-center rounded-full transition-colors", listening ? "animate-pulse bg-astra-gradient shadow-glow" : "bg-base-700 hover:bg-base-600"].join(" ")}>
            <Mic className={["h-4 w-4", listening ? "text-white" : "text-ink-300"].join(" ")} />
          </button>
          <label aria-label="Image search" className={["grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-full transition-colors", imageSelected ? "bg-astra-gradient text-white shadow-glow" : "bg-base-700 text-ink-300 hover:bg-base-600 hover:text-ink-100"].join(" ")}>
            <Camera className="h-4 w-4" />
            <input type="file" accept="image/*" className="hidden" onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) selectFile(file, "image");
            }} />
          </label>
        </div>
        <div className="hidden gap-1.5 xl:flex">
          {LANGUAGES.map((language) => (
            <button key={language} onClick={() => setLang(language)} className={["rounded-full px-3 py-1.5 text-xs font-medium transition-colors", lang === language ? "bg-astra-gradient-soft text-ink-100 shadow-[inset_0_0_0_1px_rgba(91,110,245,0.35)]" : "text-ink-500 hover:text-ink-300"].join(" ")}>
              {language}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 lg:justify-end">
        <ThemeToggle />
        <button aria-label="Notifications" className="relative grid h-9 w-9 place-items-center rounded-full bg-base-800 text-ink-300 transition-colors hover:text-ink-100">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-reject" />
        </button>
        <button className="flex items-center gap-2 rounded-full bg-base-800 py-1 pl-1 pr-2.5 text-ink-100 transition-colors hover:bg-base-700">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-astra-gradient"><User className="h-3.5 w-3.5 text-white" /></div>
          <span className="hidden text-xs font-medium md:inline">Aisha</span>
          <ChevronDown className="h-3.5 w-3.5 text-ink-500" />
        </button>
      </div>
    </header>
  );
}

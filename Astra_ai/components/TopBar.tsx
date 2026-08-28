"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Mic, Bell, ChevronDown, User, LogOut } from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import MobileNav from "@/components/MobileNav";
import { clearSession, getStoredUser } from "@/lib/auth";

const LANGUAGES = ["English", "اردو", "Roman Urdu"] as const;
const SUGGESTIONS = ["Laptop 150k ke under", "Best phone under 100k", "Mera budget check karo"];

export default function TopBar({ unreadNotifications = 0 }: { unreadNotifications?: number }) {
  const router = useRouter();
  const [lang, setLang] = useState<(typeof LANGUAGES)[number]>("Roman Urdu");
  const [listening, setListening] = useState(false);
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  // Falls back to the seeded demo user ("Aisha") until a real session exists —
  // matches the backend's get_current_user dev fallback.
  const [displayName, setDisplayName] = useState("Aisha");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored) {
      setDisplayName(stored.name);
      setLoggedIn(true);
    }
  }, []);

  function handleLogout() {
    clearSession();
    setMenuOpen(false);
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex flex-col gap-3 border-b border-base-600/60 px-4 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-8">
      <div className="flex flex-1 items-center gap-3">
        <MobileNav />
        <div className="glass glass-hover flex min-w-0 flex-1 items-center gap-3 rounded-full px-4 py-2.5">
          <Search className="h-4 w-4 text-ink-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Bolo kya chaheeye tha… (Speak or type)"
            className="flex-1 bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
          />
          <button
            onClick={() => setListening((v) => !v)}
            aria-pressed={listening}
            aria-label="Toggle voice search"
            className={[
              "grid h-8 w-8 shrink-0 place-items-center rounded-full transition-colors",
              listening ? "bg-astra-gradient shadow-glow" : "bg-base-700 hover:bg-base-600",
            ].join(" ")}
          >
            <Mic className={["h-4 w-4", listening ? "text-white" : "text-ink-300"].join(" ")} />
          </button>
        </div>

        <div className="hidden gap-1.5 xl:flex">
          {LANGUAGES.map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                lang === l
                  ? "bg-astra-gradient-soft text-ink-100 shadow-[inset_0_0_0_1px_rgba(91,110,245,0.35)]"
                  : "text-ink-500 hover:text-ink-300",
              ].join(" ")}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 lg:justify-end">
        <div className="hidden gap-2 md:flex">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setQuery(s)}
              className="whitespace-nowrap rounded-full border border-base-600 px-3 py-1.5 text-[11px] text-ink-300 transition-colors hover:border-astra-indigo/50 hover:text-ink-100"
            >
              {s}
            </button>
          ))}
        </div>

        <ThemeToggle />

        <button
          aria-label="Notifications"
          className="relative grid h-9 w-9 place-items-center rounded-full bg-base-800 text-ink-300 transition-colors hover:text-ink-100"
        >
          <Bell className="h-4 w-4" />
          {unreadNotifications > 0 && (
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-reject" />
          )}
        </button>

        {loggedIn ? (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              className="flex items-center gap-2 rounded-full bg-base-800 py-1 pl-1 pr-2.5 text-ink-100 transition-colors hover:bg-base-700"
            >
              <div className="grid h-7 w-7 place-items-center rounded-full bg-astra-gradient">
                <User className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="hidden text-xs font-medium md:inline">{displayName}</span>
              <ChevronDown className="h-3.5 w-3.5 text-ink-500" />
            </button>

            {menuOpen && (
              <div className="glass absolute right-0 top-11 z-20 w-40 overflow-hidden rounded-xl p-1">
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-ink-300 transition-colors hover:bg-base-700 hover:text-ink-100"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-2 rounded-full bg-astra-gradient py-1.5 pl-3 pr-3.5 text-xs font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
          >
            <User className="h-3.5 w-3.5" />
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}

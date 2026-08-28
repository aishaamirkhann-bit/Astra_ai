"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ShieldHalf } from "lucide-react";
import { NAV_ITEMS } from "@/lib/navItems";

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className="lg:hidden">
      <button
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-base-800 text-ink-300 hover:text-ink-100"
      >
        <Menu className="h-4 w-4" />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <aside className="glass relative flex h-full w-72 max-w-[85vw] flex-col gap-6 overflow-y-auto rounded-r-2xl border-l-0 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-astra-gradient shadow-glow">
                  <ShieldHalf className="h-5 w-5 text-white" strokeWidth={2.25} />
                </div>
                <div className="leading-tight">
                  <p className="font-display text-sm font-semibold text-ink-100">ASTRA AI</p>
                  <p className="text-[11px] text-ink-500">Trust &amp; Consent Layer</p>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="text-ink-500 hover:text-ink-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex flex-col gap-1">
              {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
                const isActive = pathname === href;
                return (
                  <Link
                    key={label}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={[
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                      isActive
                        ? "bg-astra-gradient-soft text-ink-100 shadow-[inset_0_0_0_1px_rgba(91,110,245,0.35)]"
                        : "text-ink-300 hover:bg-base-800 hover:text-ink-100",
                    ].join(" ")}
                  >
                    <Icon
                      className={["h-4 w-4", isActive ? "text-astra-cyan" : "text-ink-500"].join(" ")}
                    />
                    <span className="font-medium">{label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}
    </div>
  );
}

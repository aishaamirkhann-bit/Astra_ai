"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldHalf } from "lucide-react";
import { NAV_ITEMS } from "@/lib/navItems";

// `active` is accepted for pages that render server-side and already know
// which item should be highlighted (avoids a hydration flash); when the
// pathname is available client-side it takes priority.
export default function Sidebar({ active }: { active?: string }) {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col gap-6 border-r border-base-600/60 px-4 py-6">
      <Link href="/" className="flex items-center gap-2 px-2">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-astra-gradient shadow-glow">
          <ShieldHalf className="h-5 w-5 text-white" strokeWidth={2.25} />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold text-ink-100">ASTRA AI</p>
          <p className="text-[11px] text-ink-500">Trust &amp; Consent Layer</p>
        </div>
      </Link>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive = pathname ? pathname === href : active === label;
          return (
            <Link
              key={label}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                isActive
                  ? "bg-astra-gradient-soft text-ink-100 shadow-[inset_0_0_0_1px_rgba(91,110,245,0.35)]"
                  : "text-ink-300 hover:bg-base-800 hover:text-ink-100",
              ].join(" ")}
            >
              <Icon
                className={[
                  "h-4 w-4",
                  isActive ? "text-astra-cyan" : "text-ink-500 group-hover:text-ink-300",
                ].join(" ")}
                strokeWidth={2}
              />
              <span className="font-medium">{label}</span>
              {isActive && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-astra-cyan shadow-[0_0_8px_2px_rgba(79,209,255,0.7)]" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto glass glass-hover rounded-xl2 p-4">
        <p className="font-display text-xs font-semibold text-ink-100">Ask ASTRA</p>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-500">
          Need help deciding on a purchase? Ask in plain Roman Urdu or English.
        </p>
        <Link
          href="/messages"
          className="mt-3 block w-full rounded-lg bg-astra-gradient py-2 text-center text-xs font-semibold text-white transition-opacity hover:opacity-90"
        >
          Open ASTRA Chat
        </Link>
      </div>
    </aside>
  );
}

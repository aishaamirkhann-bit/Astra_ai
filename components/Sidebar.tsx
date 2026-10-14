"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldHalf } from "lucide-react";
import { BUYER_NAV_ITEMS, SELLER_NAV_ITEMS } from "@/lib/navItems";
import { useAccountMode } from "@/lib/useAccountMode";

// `active` is accepted for pages that render server-side and already know
// which item should be highlighted (avoids a hydration flash); when the
// pathname is available client-side it takes priority.
export default function Sidebar({ active }: { active?: string }) {
  const pathname = usePathname();
  const accountMode = useAccountMode();
  const navItems = accountMode === "seller" ? SELLER_NAV_ITEMS : BUYER_NAV_ITEMS;

  return (
    <aside className={`hidden lg:flex w-60 shrink-0 flex-col gap-6 border-r px-4 py-6 transition-colors ${
      accountMode === "seller" ? "border-purple-100/60 bg-white/45 backdrop-blur-md" : "border-base-600/60"
    }`}>
      <Link href={accountMode === "seller" ? "/seller/dashboard" : "/"} className="flex items-center gap-2 px-2">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-astra-gradient shadow-glow">
          <ShieldHalf className="h-5 w-5 text-white" strokeWidth={2.25} />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold text-ink-100">ASTRA AI</p>
          <p className="text-[11px] text-ink-500">Trust &amp; Consent Layer</p>
        </div>
      </Link>

      <nav className="flex flex-col gap-1">
        {navItems.map(({ label, href, icon: Icon }) => {
          const isActive = pathname ? pathname === href : active === label;
          return (
            <Link
              key={label}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "group flex items-center gap-3 rounded-full px-3 py-2.5 text-sm transition-all duration-200",
                isActive
                  ? accountMode === "seller"
                    ? "bg-white/85 text-ink-100 shadow-sm ring-1 ring-purple-200/70"
                    : "bg-astra-gradient-soft text-ink-100 shadow-[inset_0_0_0_1px_rgba(91,110,245,0.35)]"
                  : accountMode === "seller"
                    ? "text-ink-300 hover:bg-white/70 hover:text-ink-100"
                    : "text-ink-300 hover:bg-base-800 hover:text-ink-100",
              ].join(" ")}
            >
              <Icon
                className={[
                  "h-4 w-4",
                  isActive && accountMode === "seller"
                    ? "text-astra-violet"
                    : isActive ? "text-astra-cyan" : "text-ink-500 group-hover:text-ink-300",
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
          {accountMode === "seller" ? "Manage listings, orders, and buyer conversations from your seller workspace." : "Need help deciding on a purchase? Ask in plain Roman Urdu or English."}
        </p>
        <Link
          href={accountMode === "seller" ? "/seller/messages" : "/messages"}
          className="mt-3 block w-full rounded-lg bg-astra-gradient py-2 text-center text-xs font-semibold text-white transition-opacity hover:opacity-90"
        >
          {accountMode === "seller" ? "Open Seller Messages" : "Open ASTRA Chat"}
        </Link>
      </div>
    </aside>
  );
}

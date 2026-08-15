"use client";

import Link from "next/link";

const SUGGESTIONS = [
  { label: "Laptop 150k ke under", href: "/explore?q=laptop+150k+ke+under" },
  { label: "Best phone under 100k", href: "/explore?q=best+phone+under+100k" },
  { label: "Mera budget check karo", href: "/goals" },
];

export default function HeroBanner() {
  return (
    <section className="glass relative overflow-hidden rounded-xl2 p-6 sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-astra-gradient opacity-20 blur-3xl" />
      <p className="mb-3 inline-block rounded-full border border-base-600 px-3 py-1 text-[11px] font-medium text-ink-500">
        Every purchase, checked before it happens
      </p>
      <h1 className="font-display text-3xl font-semibold leading-tight text-ink-100 sm:text-4xl">
        Shop <span className="bg-astra-gradient bg-clip-text text-transparent">Smarter.</span>
        <br />
        Spend <span className="bg-astra-gradient bg-clip-text text-transparent">Safer.</span>
      </h1>
      <p className="mt-3 max-w-md text-sm text-ink-300">
        ASTRA AI checks affordability, seller trust, and price fairness before you buy — in
        plain language, every time.
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <Link
            key={s.label}
            href={s.href}
            className="rounded-full border border-base-600 bg-base-900/60 px-3.5 py-1.5 text-xs text-ink-300 transition-colors hover:border-astra-indigo/60 hover:text-ink-100"
          >
            &ldquo;{s.label}&rdquo;
          </Link>
        ))}
      </div>

      <div className="mt-7 flex items-center gap-4">
        <Link
          href="/explore"
          className="rounded-lg bg-astra-gradient px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90"
        >
          Start Shopping
        </Link>
        <Link
          href="/astra-check"
          className="text-sm font-medium text-ink-300 underline decoration-base-600 underline-offset-4 transition-colors hover:text-ink-100"
        >
          How ASTRA Works
        </Link>
      </div>
    </section>
  );
}

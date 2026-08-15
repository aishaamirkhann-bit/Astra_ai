"use client";

import Link from "next/link";
import { Target, Wallet2, ChevronRight } from "lucide-react";

export default function GoalsWalletRail() {
  const goalPercent = 25;

  return (
    <section className="glass glass-hover rounded-xl2 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Target className="h-3.5 w-3.5 text-astra-cyan" />
          <h2 className="font-display text-sm font-semibold text-ink-100">My Goals</h2>
        </div>
        <Link href="/goals" className="flex items-center text-[11px] text-ink-500 hover:text-ink-100">
          View all <ChevronRight className="h-3 w-3" />
        </Link>
      </div>

      <Link href="/goals" className="block">
        <p className="text-xs font-medium text-ink-100">Laptop Goal</p>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-base-800">
          <div
            className="h-full rounded-full bg-astra-gradient"
            style={{ width: `${goalPercent}%` }}
          />
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-[10px] text-ink-500">Target</p>
            <p className="text-xs font-medium text-ink-100">Rs. 180,000</p>
          </div>
          <div>
            <p className="text-[10px] text-ink-500">Allocated</p>
            <p className="text-xs font-medium text-ink-100">Rs. 45,000</p>
          </div>
          <div>
            <p className="text-[10px] text-ink-500">Remaining</p>
            <p className="text-xs font-medium text-ink-100">Rs. 135,000</p>
          </div>
        </div>
      </Link>

      <div className="my-4 h-px bg-base-600" />

      <Link href="/wallet" className="block">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Wallet2 className="h-3.5 w-3.5 text-astra-cyan" />
            <p className="text-xs font-medium text-ink-100">My Wallet</p>
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-ink-500" />
        </div>
        <p className="mt-1 text-[11px] text-ink-500">Available to spend</p>
        <p className="mt-0.5 font-display text-lg font-semibold text-ink-100">Rs. 135,000</p>
      </Link>
    </section>
  );
}

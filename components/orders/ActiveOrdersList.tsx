"use client";

import { useEffect, useState } from "react";
import { Undo2, PackageCheck, Clock } from "lucide-react";
import { ORDERS } from "@/lib/mockData";

export default function ActiveOrdersList() {
  const [countdown, setCountdown] = useState(
    Object.fromEntries(ORDERS.map((o) => [o.id, o.secondsLeft])) as Record<string, number>
  );

  useEffect(() => {
    const t = setInterval(() => {
      setCountdown((prev) => {
        const next = { ...prev };
        for (const id in next) {
          if (next[id] > 0) next[id] -= 1;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="glass rounded-xl2 p-5">
      <h2 className="mb-4 font-display text-sm font-semibold text-ink-100">Active Orders</h2>

      <div className="flex flex-col gap-3">
        {ORDERS.map((o) => {
          const secs = countdown[o.id];
          const reversible = secs > 0;
          return (
            <div
              key={o.id}
              className="flex flex-col gap-3 rounded-xl border border-base-600 bg-base-800/40 p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-base-700">
                  <PackageCheck className="h-4 w-4 text-ink-300" />
                </div>
                <div>
                  <p className="text-xs font-medium text-ink-100">{o.item}</p>
                  <p className="text-[11px] text-ink-500">
                    {o.id} · {o.price}
                  </p>
                </div>
              </div>

              {reversible ? (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 rounded-full bg-signal-hold/10 px-3 py-1.5 text-[11px] font-medium text-signal-hold">
                    <Clock className="h-3.5 w-3.5" />
                    {secs}s to reverse
                  </div>
                  <button className="flex items-center gap-1.5 rounded-lg border border-signal-reject/40 px-3 py-1.5 text-[11px] font-medium text-signal-reject hover:bg-signal-reject/10">
                    <Undo2 className="h-3.5 w-3.5" />
                    Reverse order
                  </button>
                </div>
              ) : (
                <span className="rounded-full bg-signal-good/10 px-3 py-1.5 text-[11px] font-medium text-signal-good">
                  Confirmed
                </span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Check, Undo2 } from "lucide-react";
import type { ApprovalStatusOut } from "@/lib/types";
import { approveOrder, cancelOrder } from "@/lib/api";

export default function HumanApprovalWidget({ approval }: { approval: ApprovalStatusOut | null }) {
  const [secondsLeft, setSecondsLeft] = useState(approval?.seconds_left ?? 0);
  const [resolved, setResolved] = useState<"pending" | "approved" | "cancelled">("pending");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!approval || resolved !== "pending") return;
    if (secondsLeft <= 0) return;
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft, resolved, approval]);

  if (!approval) {
    return (
      <section className="glass glass-hover rounded-xl2 border-signal-hold/20 p-5">
        <div className="mb-2 flex items-center gap-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-ink-500" />
          <h2 className="font-display text-sm font-semibold text-ink-100">Human Approval</h2>
        </div>
        <p className="text-xs text-ink-500">No order is currently waiting on your approval.</p>
      </section>
    );
  }

  const progress = (secondsLeft / approval.window_seconds) * 100;

  async function handleApprove() {
    setBusy(true);
    try {
      await approveOrder(approval!.order_ref);
      setResolved("approved");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    setBusy(true);
    try {
      await cancelOrder(approval!.order_ref);
      setResolved("cancelled");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="glass glass-hover rounded-xl2 border-signal-hold/20 p-5">
      <div className="mb-3 flex items-center gap-1.5">
        <AlertTriangle className="h-3.5 w-3.5 text-signal-hold" />
        <h2 className="font-display text-sm font-semibold text-ink-100">
          Human Approval Required
        </h2>
      </div>

      {resolved === "pending" ? (
        <>
          <p className="mb-4 text-xs text-ink-300">{approval.prompt_text}</p>

          <div className="relative mx-auto grid h-24 w-24 place-items-center">
            <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="44"
                fill="none"
                stroke="rgb(var(--base-600))"
                strokeWidth="6"
              />
              <circle
                cx="50"
                cy="50"
                r="44"
                fill="none"
                stroke="url(#approvalGradient)"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={2 * Math.PI * 44}
                strokeDashoffset={2 * Math.PI * 44 * (1 - progress / 100)}
                style={{ transition: "stroke-dashoffset 1s linear" }}
              />
              <defs>
                <linearGradient id="approvalGradient" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#5B6EF5" />
                  <stop offset="100%" stopColor="#9B6BFF" />
                </linearGradient>
              </defs>
            </svg>
            <div className="text-center">
              <p className="font-display text-2xl font-bold text-ink-100">{secondsLeft}</p>
              <p className="text-[10px] text-ink-500">seconds</p>
            </div>
          </div>

          <button
            onClick={handleApprove}
            disabled={busy}
            className="mt-5 flex w-full items-center justify-center gap-1.5 rounded-lg bg-astra-gradient py-2.5 text-xs font-semibold text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            <Check className="h-3.5 w-3.5" /> Approve Transaction
          </button>
          <button
            onClick={handleCancel}
            disabled={busy}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-base-600 py-2.5 text-xs font-medium text-ink-300 transition-colors hover:border-signal-reject/50 hover:text-signal-reject disabled:opacity-60"
          >
            <Undo2 className="h-3.5 w-3.5" /> Cancel &amp; Refund
          </button>

          <p className="mt-3 text-center text-[10px] text-ink-700">
            You can reverse this order within {approval.window_seconds} seconds.
          </p>
        </>
      ) : (
        <div className="grid place-items-center gap-2 py-8 text-center">
          <div
            className={[
              "grid h-12 w-12 place-items-center rounded-full",
              resolved === "approved" ? "bg-signal-good/10" : "bg-signal-reject/10",
            ].join(" ")}
          >
            {resolved === "approved" ? (
              <Check className="h-5 w-5 text-signal-good" />
            ) : (
              <Undo2 className="h-5 w-5 text-signal-reject" />
            )}
          </div>
          <p className="text-xs font-medium text-ink-100">
            {resolved === "approved" ? "Transaction approved" : "Order cancelled — refund started"}
          </p>
          <Link href="/orders" className="text-[11px] font-medium text-ink-500 hover:text-ink-100">
            View in Orders →
          </Link>
        </div>
      )}
    </section>
  );
}

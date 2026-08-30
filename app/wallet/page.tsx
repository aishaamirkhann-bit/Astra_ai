"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Wallet2, ArrowDownLeft, ArrowUpRight, Target, Loader2, Radio, Sparkles } from "lucide-react";
import PageShell from "@/components/PageShell";
import { getWallet, getGoals, getWalletWebSocketUrl, topUpWallet, withdrawFromWallet } from "@/lib/api";
import type { WalletDetailOut, GoalOut } from "@/lib/types";

export default function WalletPage() {
  const [wallet, setWallet] = useState<WalletDetailOut | null>(null);
  const [goals, setGoals] = useState<GoalOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Top up / withdraw inline forms
  const [mode, setMode] = useState<"topup" | "withdraw" | null>(null);
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    const [w, g] = await Promise.all([getWallet(), getGoals()]);
    setWallet(w);
    setGoals(g.filter((goal) => goal.cadence_amount));
  }

  useEffect(() => {
    setLoading(true);
    refresh()
      .catch(() => setError("Could not load wallet."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!wallet?.user_id) return;
    const socket = new WebSocket(getWalletWebSocketUrl(wallet.user_id));
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string };
      if (event.type === "balance_updated") void refresh();
    };
    const ping = window.setInterval(() => socket.readyState === WebSocket.OPEN && socket.send("ping"), 20000);
    return () => { window.clearInterval(ping); socket.close(); };
  }, [wallet?.user_id]);

  async function handleSubmit() {
    const value = Number(amount);
    if (!value || value <= 0 || !mode) return;
    setError(null);
    setSubmitting(true);
    try {
      const updated = mode === "topup" ? await topUpWallet(value) : await withdrawFromWallet(value);
      setWallet(updated);
      setMode(null);
      setAmount("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      setError(mode === "withdraw" && message.includes("400") ? "Balance itni nahi hai." : "Transaction fail ho gayi.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageShell
      active="Wallet"
      title="Wallet"
      subtitle="Your available balance, ledger history, and contribution schedules."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-5">
          <section className="glass rounded-xl2 p-5">
            <div className="mb-1 flex items-center gap-2">
              <Wallet2 className="h-4 w-4 text-astra-cyan" />
              <p className="text-xs font-medium text-ink-300">Available to spend</p>
            </div>
            <p className="font-display text-3xl font-bold text-ink-100">
              {loading || !wallet ? "…" : wallet.available_balance_display}
            </p>
            <div className="mt-3 flex items-center justify-between"><span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[9px] font-semibold uppercase tracking-wider text-emerald-400">PKR wallet</span><span className="flex items-center gap-1 text-[9px] text-emerald-400"><Radio className="h-3 w-3 animate-pulse" /> Live balance</span></div>

            {error && (
              <p className="mt-3 rounded-lg bg-signal-reject/10 px-3 py-2 text-xs font-medium text-signal-reject">
                {error}
              </p>
            )}

            {mode ? (
              <div className="mt-4 flex flex-col gap-2">
                <input
                  type="number"
                  min={1}
                  autoFocus
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Amount"
                  className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
                />
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={handleSubmit}
                    disabled={submitting}
                    className="flex items-center justify-center gap-1.5 rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-60"
                  >
                    {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Confirm
                  </button>
                  <button
                    onClick={() => {
                      setMode(null);
                      setAmount("");
                      setError(null);
                    }}
                    className="rounded-lg border border-base-600 py-2 text-xs font-medium text-ink-300 hover:text-ink-100"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  onClick={() => setMode("topup")}
                  className="rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white hover:opacity-90"
                >
                  Top Up
                </button>
                <button
                  onClick={() => setMode("withdraw")}
                  className="rounded-lg border border-base-600 py-2 text-xs font-medium text-ink-300 hover:text-ink-100"
                >
                  Withdraw
                </button>
              </div>
            )}
          </section>

          <section className="glass rounded-xl2 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Target className="h-4 w-4 text-astra-cyan" />
              <p className="text-xs font-medium text-ink-100">Active goal contributions</p>
            </div>
            <div className="flex flex-col gap-3 text-[11px]">
              {goals.length === 0 ? (
                <p className="text-ink-500">Koi active contribution schedule nahi hai.</p>
              ) : (
                goals.map((g) => (
                  <div key={g.id} className="flex items-center justify-between">
                    <span className="text-ink-300">{g.name}</span>
                    <span className="font-mono text-ink-500">
                      Rs. {g.cadence_amount?.toLocaleString()} / {g.cadence_period === "weekly" ? "week" : "month"}
                    </span>
                  </div>
                ))
              )}
            </div>
            <Link
              href="/my-goals"
              className="mt-4 inline-block text-[11px] font-medium text-ink-500 hover:text-ink-100"
            >
              Manage goals →
            </Link>
          </section>
        </div>

        <section className="glass rounded-xl2 p-5">
          <h2 className="mb-4 font-display text-sm font-semibold text-ink-100">
            Ledger history
          </h2>
          {loading || !wallet ? (
            <p className="text-xs text-ink-500">Loading…</p>
          ) : wallet.ledger.length === 0 ? (
            <p className="text-xs text-ink-500">Abhi koi transaction nahi hai.</p>
          ) : (
            <div className="flex flex-col divide-y divide-base-700">
              {wallet.ledger.map((t) => (
                <div key={t.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={[
                        "grid h-8 w-8 shrink-0 place-items-center rounded-full",
                        t.entry_type === "credit" ? "bg-signal-good/10" : "bg-signal-reject/10",
                      ].join(" ")}
                    >
                      {t.entry_type === "credit" ? (
                        <ArrowDownLeft className="h-3.5 w-3.5 text-signal-good" />
                      ) : (
                        <ArrowUpRight className="h-3.5 w-3.5 text-signal-reject" />
                      )}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><p className="text-xs font-medium text-ink-100">{t.label}</p><span className={`rounded-full px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider ${t.transaction_type === "Debit" ? "bg-rose-500/10 text-rose-400" : t.transaction_type === "Refund" ? "bg-cyan-500/10 text-cyan-400" : t.label.toLowerCase().includes("cashback") ? "bg-violet-500/10 text-violet-400" : "bg-emerald-500/10 text-emerald-400"}`}>{t.label.toLowerCase().includes("cashback") ? <span className="inline-flex items-center gap-1"><Sparkles className="h-2.5 w-2.5" /> AI Deal Cashback</span> : t.transaction_type}</span></div>
                      <p className="text-[10px] text-ink-500">
                        {new Date(t.created_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                    </div>
                  </div>
                  <p
                    className={[
                      "font-display text-sm font-semibold",
                      t.entry_type === "credit" ? "text-signal-good" : "text-signal-reject",
                    ].join(" ")}
                  >
                    {t.entry_type === "credit" ? "+" : "−"} Rs. {Math.abs(t.amount).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </PageShell>
  );
}

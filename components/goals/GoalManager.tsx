"use client";

import { useEffect, useState } from "react";
import { Target, Plus, X, Wallet2, Loader2, Trash2, PiggyBank } from "lucide-react";
import { getGoals, createGoal, deleteGoal, allocateToGoal, getWalletSummary } from "@/lib/api";
import type { GoalOut, CadencePeriod } from "@/lib/types";

export default function GoalManager() {
  const [goals, setGoals] = useState<GoalOut[]>([]);
  const [walletBalance, setWalletBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allocatingId, setAllocatingId] = useState<number | null>(null);
  const [allocateAmount, setAllocateAmount] = useState("");

  // New-goal form fields
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [deadline, setDeadline] = useState("");
  const [cadencePeriod, setCadencePeriod] = useState<CadencePeriod>("weekly");
  const [cadenceAmount, setCadenceAmount] = useState("");

  async function refresh() {
    const [g, w] = await Promise.all([getGoals(), getWalletSummary()]);
    setGoals(g);
    setWalletBalance(w.available_balance);
  }

  useEffect(() => {
    setLoading(true);
    refresh()
      .catch(() => setError("Could not load goals/wallet."))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !target) {
      setError("Goal name aur target amount required hain.");
      return;
    }
    setSubmitting(true);
    try {
      await createGoal({
        name: name.trim(),
        target_amount: Number(target),
        deadline: deadline || null,
        cadence_amount: cadenceAmount ? Number(cadenceAmount) : null,
        cadence_period: cadenceAmount ? cadencePeriod : null,
      });
      setName("");
      setTarget("");
      setDeadline("");
      setCadenceAmount("");
      setShowForm(false);
      await refresh();
    } catch {
      setError("Goal create nahi ho saka. Dobara try karein.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(goalId: number) {
    try {
      await deleteGoal(goalId);
      await refresh();
    } catch {
      setError("Goal delete nahi ho saka.");
    }
  }

  async function handleAllocate(goalId: number) {
    const amount = Number(allocateAmount);
    if (!amount || amount <= 0) return;
    setError(null);
    try {
      await allocateToGoal(goalId, amount);
      setAllocatingId(null);
      setAllocateAmount("");
      await refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      setError(message.includes("400") ? "Wallet balance itna nahi hai." : "Contribution save nahi hui.");
    }
  }

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet2 className="h-4 w-4 text-astra-cyan" />
          <div>
            <h2 className="font-display text-sm font-semibold text-ink-100">My Wallet</h2>
            <p className="font-display text-lg font-bold text-ink-100">
              {walletBalance === null ? "…" : `Rs. ${walletBalance.toLocaleString()}`}
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg bg-astra-gradient px-3.5 py-2 text-xs font-semibold text-white hover:opacity-90"
        >
          {showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {showForm ? "Cancel" : "New Goal"}
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-lg bg-signal-reject/10 px-3 py-2 text-xs font-medium text-signal-reject">
          {error}
        </p>
      )}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-base-600 bg-base-800/50 p-4 sm:grid-cols-2"
        >
          <div className="sm:col-span-2">
            <label className="mb-1 block text-[11px] text-ink-500">Goal name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. New Phone Fund"
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-500">Target amount</label>
            <input
              type="number"
              min={1}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="200000"
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-500">Target date</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 focus:outline-none"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-[11px] text-ink-500">Contribution schedule (optional)</label>
            <div className="flex gap-2">
              <select
                value={cadencePeriod}
                onChange={(e) => setCadencePeriod(e.target.value as CadencePeriod)}
                className="flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 focus:outline-none"
              >
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
              <input
                type="number"
                min={0}
                value={cadenceAmount}
                onChange={(e) => setCadenceAmount(e.target.value)}
                placeholder="Amount"
                className="flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="sm:col-span-2 mt-1 flex items-center justify-center gap-2 rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create Goal
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-xs text-ink-500">Loading goals…</p>
      ) : goals.length === 0 ? (
        <p className="text-xs text-ink-500">Abhi koi goal nahi hai — &quot;New Goal&quot; se shuru karein.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {goals.map((g) => (
            <div key={g.id} className="rounded-xl border border-base-600 bg-base-800/40 p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Target className="h-3.5 w-3.5 text-astra-violet" />
                  <p className="text-xs font-semibold text-ink-100">{g.name}</p>
                </div>
                <div className="flex items-center gap-3">
                  {g.deadline && <p className="text-[11px] text-ink-500">Due {g.deadline}</p>}
                  <button
                    onClick={() => handleDelete(g.id)}
                    className="text-ink-700 hover:text-signal-reject"
                    title="Delete goal"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="mb-1.5 h-2 w-full overflow-hidden rounded-full bg-base-700">
                <div
                  className="h-full rounded-full bg-astra-gradient"
                  style={{ width: `${Math.min(g.percent_funded, 100)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-ink-500">
                <span>
                  Rs. {g.allocated_amount.toLocaleString()} of Rs. {g.target_amount.toLocaleString()} (
                  {g.percent_funded}%)
                </span>
                {g.cadence_amount && (
                  <span className="font-mono text-astra-cyan">
                    Rs. {g.cadence_amount.toLocaleString()} / {g.cadence_period === "weekly" ? "week" : "month"}
                  </span>
                )}
              </div>

              {allocatingId === g.id ? (
                <div className="mt-3 flex gap-2">
                  <input
                    type="number"
                    min={1}
                    autoFocus
                    value={allocateAmount}
                    onChange={(e) => setAllocateAmount(e.target.value)}
                    placeholder="Amount"
                    className="flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-1.5 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
                  />
                  <button
                    onClick={() => handleAllocate(g.id)}
                    className="rounded-lg bg-astra-gradient px-3 py-1.5 text-[11px] font-semibold text-white hover:opacity-90"
                  >
                    Add
                  </button>
                  <button
                    onClick={() => {
                      setAllocatingId(null);
                      setAllocateAmount("");
                    }}
                    className="rounded-lg border border-base-600 px-3 py-1.5 text-[11px] text-ink-500 hover:text-ink-100"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setAllocatingId(g.id)}
                  className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-ink-500 hover:text-ink-100"
                >
                  <PiggyBank className="h-3.5 w-3.5" />
                  Add funds from wallet
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

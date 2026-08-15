"use client";

import { useState } from "react";
import { Target, Plus, X, Wallet2 } from "lucide-react";

const GOALS = [
  { name: "Laptop Goal", target: 180000, saved: 45000, deadline: "Dec 2026", cadence: "Rs. 8,000 / week" },
  { name: "Umrah Fund", target: 450000, saved: 120000, deadline: "Jun 2027", cadence: "Rs. 25,000 / month" },
];

export default function GoalManager() {
  const [showForm, setShowForm] = useState(false);

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet2 className="h-4 w-4 text-astra-cyan" />
          <div>
            <h2 className="font-display text-sm font-semibold text-ink-100">My Wallet</h2>
            <p className="font-display text-lg font-bold text-ink-100">Rs. 135,000</p>
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

      {showForm && (
        <div className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-base-600 bg-base-800/50 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-[11px] text-ink-500">Goal name</label>
            <input
              placeholder="e.g. New Phone Fund"
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-500">Target amount</label>
            <input
              placeholder="Rs. 200,000"
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] text-ink-500">Target date</label>
            <input
              type="date"
              className="w-full rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 focus:outline-none"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-[11px] text-ink-500">Contribution schedule</label>
            <div className="flex gap-2">
              <select className="flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 focus:outline-none">
                <option>Weekly</option>
                <option>Monthly</option>
              </select>
              <input
                placeholder="Amount"
                className="flex-1 rounded-lg border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-100 placeholder:text-ink-700 focus:outline-none"
              />
            </div>
          </div>
          <button className="sm:col-span-2 mt-1 rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white hover:opacity-90">
            Create Goal
          </button>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {GOALS.map((g) => {
          const pct = Math.round((g.saved / g.target) * 100);
          return (
            <div key={g.name} className="rounded-xl border border-base-600 bg-base-800/40 p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Target className="h-3.5 w-3.5 text-astra-violet" />
                  <p className="text-xs font-semibold text-ink-100">{g.name}</p>
                </div>
                <p className="text-[11px] text-ink-500">Due {g.deadline}</p>
              </div>
              <div className="mb-1.5 h-2 w-full overflow-hidden rounded-full bg-base-700">
                <div
                  className="h-full rounded-full bg-astra-gradient"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-ink-500">
                <span>
                  Rs. {g.saved.toLocaleString()} of Rs. {g.target.toLocaleString()} ({pct}%)
                </span>
                <span className="font-mono text-astra-cyan">{g.cadence}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

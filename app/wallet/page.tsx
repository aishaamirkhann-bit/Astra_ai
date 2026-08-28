import Link from "next/link";
import { Wallet2, ArrowDownLeft, ArrowUpRight, Target } from "lucide-react";
import PageShell from "@/components/PageShell";
import { WALLET_LEDGER } from "@/lib/mockData";

export default function WalletPage() {
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
            <p className="font-display text-3xl font-bold text-ink-100">Rs. 25,000</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button className="rounded-lg bg-astra-gradient py-2 text-xs font-semibold text-white hover:opacity-90">
                Top Up
              </button>
              <button className="rounded-lg border border-base-600 py-2 text-xs font-medium text-ink-300 hover:text-ink-100">
                Withdraw
              </button>
            </div>
          </section>

          <section className="glass rounded-xl2 p-5">
            <div className="mb-3 flex items-center gap-2">
              <Target className="h-4 w-4 text-astra-cyan" />
              <p className="text-xs font-medium text-ink-100">Active goal contributions</p>
            </div>
            <div className="flex flex-col gap-3 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-ink-300">Laptop Goal</span>
                <span className="font-mono text-ink-500">Rs. 8,000 / week</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-300">Umrah Fund</span>
                <span className="font-mono text-ink-500">Rs. 25,000 / month</span>
              </div>
            </div>
            <Link
              href="/goals"
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
          <div className="flex flex-col divide-y divide-base-700">
            {WALLET_LEDGER.map((t) => (
              <div key={t.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div
                    className={[
                      "grid h-8 w-8 shrink-0 place-items-center rounded-full",
                      t.type === "credit" ? "bg-signal-good/10" : "bg-signal-reject/10",
                    ].join(" ")}
                  >
                    {t.type === "credit" ? (
                      <ArrowDownLeft className="h-3.5 w-3.5 text-signal-good" />
                    ) : (
                      <ArrowUpRight className="h-3.5 w-3.5 text-signal-reject" />
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-ink-100">{t.label}</p>
                    <p className="text-[10px] text-ink-500">
                      {t.id} · {t.date}
                    </p>
                  </div>
                </div>
                <p
                  className={[
                    "font-display text-sm font-semibold",
                    t.type === "credit" ? "text-signal-good" : "text-signal-reject",
                  ].join(" ")}
                >
                  {t.type === "credit" ? "+" : "−"} Rs. {Math.abs(t.amount).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </PageShell>
  );
}

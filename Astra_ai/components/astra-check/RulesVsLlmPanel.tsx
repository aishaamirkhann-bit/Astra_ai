import { Cpu, Sparkles, ArrowRight } from "lucide-react";

const RULE_CHECKS = [
  { label: "Available balance ≥ item price", pass: true },
  { label: "Weekly spend cap not exceeded", pass: true },
  { label: "Category risk flag absent", pass: true },
  { label: "Active savings goal not raided", pass: true },
];

export default function RulesVsLlmPanel() {
  return (
    <section className="glass rounded-xl2 p-5">
      <h2 className="mb-1 font-display text-sm font-semibold text-ink-100">
        Deterministic Rules vs. LLM Explanation
      </h2>
      <p className="mb-5 text-xs text-ink-500">
        The verdict is decided by fixed rules first. The LLM only explains — it never overrides.
      </p>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
        {/* Rules engine */}
        <div className="rounded-xl border border-base-600 bg-base-800/50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center rounded-lg bg-astra-gradient-soft">
              <Cpu className="h-3.5 w-3.5 text-astra-cyan" />
            </div>
            <p className="text-xs font-semibold text-ink-100">Rules Engine (deterministic)</p>
          </div>
          <ul className="flex flex-col gap-2">
            {RULE_CHECKS.map((r) => (
              <li key={r.label} className="flex items-center justify-between text-[11px]">
                <span className="text-ink-300">{r.label}</span>
                <span className="rounded-full bg-signal-good/10 px-2 py-0.5 font-semibold text-signal-good">
                  Pass
                </span>
              </li>
            ))}
          </ul>
        </div>

        <ArrowRight className="mx-auto hidden h-5 w-5 text-ink-700 md:block" />

        {/* LLM layer */}
        <div className="rounded-xl border border-base-600 bg-base-800/50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center rounded-lg bg-astra-gradient-soft">
              <Sparkles className="h-3.5 w-3.5 text-astra-violet" />
            </div>
            <p className="text-xs font-semibold text-ink-100">LLM Explanation Layer</p>
          </div>
          <p className="text-[11px] leading-relaxed text-ink-300">
            "This Samsung Galaxy S25 Ultra fits comfortably within your remaining budget, the
            seller has a strong trust history, and the price sits below the market average for
            this model. No contradictions were found with your active Laptop savings goal."
          </p>
          <p className="mt-3 text-[10px] uppercase tracking-wide text-ink-700">
            Generated after rules pass — cannot change the verdict
          </p>
        </div>
      </div>
    </section>
  );
}

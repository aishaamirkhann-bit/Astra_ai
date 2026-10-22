"use client";

import { useState, type FormEvent } from "react";
import { createDistributionEntry, getKhataAlert, type KhataAlert } from "@/lib/api";

const money = (amount: number) => `Rs. ${Math.round(amount).toLocaleString("en-PK")}`;

export default function DistributionLedgerPanel() {
  const [alert, setAlert] = useState<KhataAlert | null>(null);
  const [retailerId, setRetailerId] = useState("");
  const [entryType, setEntryType] = useState<"sale" | "repayment">("sale");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadAlert(id = retailerId) {
    if (!id || Number(id) < 1) { setError("Enter a valid retailer account ID."); return; }
    setError("");
    try { setAlert(await getKhataAlert(Number(id))); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load this retailer ledger."); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement = event.currentTarget; const values = new FormData(formElement);
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await createDistributionEntry({
        retailer_id: Number(retailerId), entry_type: entryType,
        transaction_amount: Number(values.get("amount")),
        credit_amount: entryType === "sale" ? Number(values.get("credit")) : 0,
        credit_limit: entryType === "sale" ? Number(values.get("limit")) : 0,
        reference: String(values.get("reference") ?? ""),
      });
      setNotice(entryType === "sale" ? `Ledger entry recorded. Platform commission tracked: ${money(result.commission_amount)}.` : "Repayment recorded against the outstanding khata balance.");
      formElement.reset(); await loadAlert();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save the distribution ledger entry."); }
    finally { setBusy(false); }
  }

  const riskColor = alert?.khata_risk_status === "over_limit" || alert?.khata_risk_status === "high" ? "text-rose-300" : alert?.khata_risk_status === "watch" ? "text-amber-200" : "text-emerald-300";
  return <section className="rounded-2xl border border-base-700 bg-base-900/60 p-5">
    <div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-300">Distribution &amp; khata</p><h2 className="mt-1 font-display text-base font-bold text-ink-100">Retailer credit and stock signals</h2><p className="mt-1 text-[10px] leading-relaxed text-ink-500">Record a distribution sale or repayment. Replenishment is an alert only; no order or credit decision is made automatically.</p></div>
    <form onSubmit={(event) => void submit(event)} className="mt-4 grid gap-3 md:grid-cols-2">
      <label className="text-[10px] text-ink-400">Retailer account ID<input type="number" required min="1" value={retailerId} onChange={(event) => setRetailerId(event.target.value)} className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100" /></label>
      <label className="text-[10px] text-ink-400">Entry type<select value={entryType} onChange={(event) => setEntryType(event.target.value as "sale" | "repayment")} className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100"><option value="sale">Distribution sale</option><option value="repayment">Khata repayment</option></select></label>
      <label className="text-[10px] text-ink-400">{entryType === "sale" ? "Distribution value (PKR)" : "Repayment amount (PKR)"}<input name="amount" type="number" required min="0.01" step="0.01" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100" /></label>
      {entryType === "sale" && <><label className="text-[10px] text-ink-400">Khata credit extended (PKR)<input name="credit" type="number" min="0" step="0.01" defaultValue="0" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100" /></label><label className="text-[10px] text-ink-400">Retailer credit limit (PKR)<input name="limit" type="number" min="0" step="0.01" defaultValue="0" className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100" /></label></>}
      <label className="text-[10px] text-ink-400">Reference (optional)<input name="reference" maxLength={120} className="mt-1 w-full rounded-lg border border-base-600 bg-base-800 px-3 py-2.5 text-xs text-ink-100" /></label>
      <div className="flex flex-wrap items-end gap-2 md:col-span-2"><button disabled={busy} className="rounded-lg bg-astra-gradient px-4 py-2.5 text-[11px] font-bold text-white disabled:opacity-50">{busy ? "Saving…" : "Record ledger entry"}</button><button type="button" onClick={() => void loadAlert()} className="rounded-lg border border-base-600 px-4 py-2.5 text-[11px] font-semibold text-ink-200">Check retailer alerts</button></div>
    </form>
    {error && <p role="alert" className="mt-3 text-xs text-rose-300">{error}</p>}{notice && <p role="status" className="mt-3 text-xs text-emerald-300">{notice}</p>}
    {alert && <div className="mt-4 rounded-xl border border-base-700 bg-base-800/60 p-4">
      <div className="grid gap-3 sm:grid-cols-4"><div><p className="text-[9px] uppercase text-ink-500">Khata outstanding</p><p className="mt-1 text-sm font-bold text-ink-100">{money(alert.khata_outstanding)}</p></div><div><p className="text-[9px] uppercase text-ink-500">Credit limit</p><p className="mt-1 text-sm font-bold text-ink-100">{money(alert.credit_limit)}</p></div><div><p className="text-[9px] uppercase text-ink-500">Utilization</p><p className="mt-1 text-sm font-bold text-ink-100">{alert.credit_utilization_percent}%</p></div><div><p className="text-[9px] uppercase text-ink-500">Risk status</p><p className={`mt-1 text-sm font-bold capitalize ${riskColor}`}>{alert.khata_risk_status.replace("_", " ")}</p></div></div>
      <div className="mt-4 border-t border-base-700 pt-3"><p className="text-[10px] font-semibold text-ink-200">Low-stock replenishment alerts</p>{alert.low_stock_alerts.length ? <ul className="mt-2 grid gap-1 sm:grid-cols-2">{alert.low_stock_alerts.map((item) => <li key={item.product_id} className="flex justify-between gap-2 text-[10px] text-ink-400"><span>{item.title} · {item.stock_count} left</span><span className="text-amber-200">Suggest +{item.replenish_suggested}</span></li>)}</ul> : <p className="mt-1 text-[10px] text-ink-500">No low-stock listings found.</p>}</div>
    </div>}
  </section>;
}

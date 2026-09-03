"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Globe2, KeyRound, Loader2, Mic, ShieldCheck, X } from "lucide-react";
import { authorizeFinancialConsent, getMicroSettlements } from "@/lib/api";
import type { MicroSettlements } from "@/lib/types";

type FinancialConsentModalProps = {
  open: boolean;
  amount: number;
  onClose: () => void;
  onAuthorized: (consentId: string) => Promise<void>;
  initialTab?: "Voice" | "OTP";
} & ({ orderRef: string; checkoutRef?: never } | { checkoutRef: string; orderRef?: never });

export default function FinancialConsentModal(props: FinancialConsentModalProps) {
  const { open, amount, onClose, onAuthorized, initialTab = "Voice" } = props;
  const reference = props.checkoutRef ?? props.orderRef ?? "this purchase";
  const [tab, setTab] = useState<"Voice" | "OTP">(initialTab);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [otp, setOtp] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [devOtp, setDevOtp] = useState("");
  const [error, setError] = useState("");
  const [settlements, setSettlements] = useState<MicroSettlements | null>(null);

  async function authorize(payload: { auth_method: "Voice" | "OTP"; voice_transcript?: string; consent_id?: string; otp_code?: string }) {
    if (props.checkoutRef) return authorizeFinancialConsent({ amount, ...payload, checkout_ref: props.checkoutRef });
    return authorizeFinancialConsent({ amount, ...payload, order_ref: props.orderRef! });
  }

  useEffect(() => { if (!open) { setOtp(""); setChallengeId(""); setDevOtp(""); setError(""); setRecording(false); setSettlements(null); } else { setTab(initialTab); } }, [open, initialTab, reference]);

  useEffect(() => {
    if (!open || amount <= 0) return;
    let live = true;
    getMicroSettlements(amount).then((result) => { if (live) setSettlements(result); }).catch(() => undefined);
    return () => { live = false; };
  }, [open, amount]);

  async function finishVoice() {
    setRecording(false); setBusy(true); setError("");
    try {
      const phrase = `I authorize payment of Rs. ${Math.round(amount)}`;
      const result = await authorize({ auth_method: "Voice", voice_transcript: phrase });
      await onAuthorized(result.consent_id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Voice authorization failed"); } finally { setBusy(false); }
  }

  async function startVoice() {
    setError("");
    try { const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); stream.getTracks().forEach((track) => track.stop()); setRecording(true); }
    catch { setError("Microphone access is required. You can use OTP instead."); }
  }

  async function handleOtp() {
    setBusy(true); setError("");
    try {
      if (!challengeId) {
        const result = await authorize({ auth_method: "OTP" });
        setChallengeId(result.consent_id); setDevOtp(result.dev_otp ?? "");
      } else {
        const result = await authorize({ auth_method: "OTP", consent_id: challengeId, otp_code: otp });
        await onAuthorized(result.consent_id);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "OTP authorization failed"); } finally { setBusy(false); }
  }

  return <AnimatePresence>{open && <motion.div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/75 p-4 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <motion.section role="dialog" aria-modal="true" aria-labelledby="consent-title" initial={{ opacity: 0, scale: .94, y: 24 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .96 }} className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-3xl border border-violet-400/25 bg-slate-950/95 shadow-2xl">
      <div className="relative border-b border-white/10 bg-gradient-to-br from-violet-500/20 via-cyan-500/5 to-transparent p-6">
        <button onClick={onClose} className="absolute right-4 top-4 rounded-full p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close"><X className="h-4 w-4" /></button>
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-violet-500/20 text-violet-300"><ShieldCheck className="h-6 w-6" /></span>
        <h2 id="consent-title" className="mt-4 font-display text-xl font-bold text-white">Financial consent required</h2>
        <p className="mt-1 text-sm text-slate-400">Securely authorize <strong className="text-white">Rs. {amount.toLocaleString()}</strong> for {reference}.</p>
      </div>
      <div className="p-4 sm:p-6">
        <div className="grid grid-cols-2 rounded-xl bg-slate-900 p-1"><button onClick={() => setTab("Voice")} className={`rounded-lg py-2 text-xs font-semibold ${tab === "Voice" ? "bg-violet-500 text-white" : "text-slate-400"}`}>Voice consent</button><button onClick={() => setTab("OTP")} className={`rounded-lg py-2 text-xs font-semibold ${tab === "OTP" ? "bg-violet-500 text-white" : "text-slate-400"}`}>6-digit OTP</button></div>
        {tab === "Voice" ? <div className="mt-6 text-center">
          <button disabled={busy} onPointerDown={() => void startVoice()} onPointerUp={() => recording && void finishVoice()} onPointerLeave={() => recording && void finishVoice()} className={`relative mx-auto grid h-24 w-24 place-items-center rounded-full transition ${recording ? "bg-rose-500 text-white shadow-[0_0_45px_rgba(244,63,94,.45)]" : "bg-violet-500/15 text-violet-300"}`}>
            {busy ? <Loader2 className="h-8 w-8 animate-spin" /> : <Mic className="h-8 w-8" />}
            {recording && [0,1,2].map((i) => <motion.i key={i} className="absolute inset-0 rounded-full border border-rose-400" animate={{ scale: [1, 1.55], opacity: [0.8, 0] }} transition={{ duration: 1.4, repeat: Infinity, delay: i * .35 }} />)}
          </button>
          <p className="mt-5 text-xs font-semibold text-white">Hold to say:</p><p className="mt-1 text-xs text-slate-400">“I authorize payment of Rs. {Math.round(amount).toLocaleString()}”</p>
          <div className="mt-5 flex h-8 items-center justify-center gap-1">{Array.from({ length: 18 }).map((_, i) => <motion.i key={i} className="w-1 rounded-full bg-cyan-400" animate={{ height: recording ? [5, 10 + (i % 6) * 3, 5] : 4 }} transition={{ repeat: Infinity, duration: .55, delay: i * .025 }} />)}</div>
        </div> : <div className="mt-6">
          {!challengeId ? <button disabled={busy} onClick={() => void handleOtp()} className="flex w-full items-center justify-center gap-2 rounded-xl bg-astra-gradient py-3 text-sm font-bold text-white"><KeyRound className="h-4 w-4" /> Send secure OTP</button> : <><p className="text-center text-xs text-slate-400">Enter the code sent to your verified contact.</p><div className="mt-4 flex justify-center"><input autoFocus inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} className="w-52 rounded-xl border border-violet-400/30 bg-slate-900 px-4 py-3 text-center font-mono text-2xl tracking-[.45em] text-white outline-none focus:border-violet-400" /></div>{devOtp && <p className="mt-2 text-center text-[10px] text-amber-300">Demo code: {devOtp}</p>}<button disabled={busy || otp.length !== 6} onClick={() => void handleOtp()} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-astra-gradient py-3 text-sm font-bold text-white disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Authorize & complete order</button></>}
        </div>}
        {error && <p className="mt-4 rounded-xl bg-rose-500/10 p-3 text-xs text-rose-300">{error}</p>}
        {settlements && <div className="mt-4 rounded-xl border border-white/10 bg-slate-900/70 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-cyan-300"><Globe2 className="h-3 w-3" /> Cross-border micro-escrow</span>
            <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-[10px] font-bold text-emerald-300">Total fee Rs. {settlements.total_fee.toLocaleString()} · Zero-FX</span>
          </div>
          <p className="mt-1 text-[10px] text-slate-500">{settlements.corridor} · slippage {settlements.fx_slippage_percent}% · ref {settlements.reference}</p>
          <div className="mt-2 space-y-1">
            {settlements.routes.map((hop, index) => <div key={index} className="flex items-center justify-between gap-2 rounded-lg bg-slate-950/60 px-2 py-1 font-mono text-[10px] text-slate-400">
              <span>{hop.from} → {hop.to} <span className="text-slate-600">via {hop.via}</span></span>
              <span className="text-slate-300">@{hop.rate} · {hop.latency_ms}ms · {hop.status}</span>
            </div>)}
          </div>
        </div>}
        <p className="mt-5 text-center text-[10px] text-slate-500">Encrypted authorization · Amount-bound · Single-use</p>
      </div>
    </motion.section>
  </motion.div>}</AnimatePresence>;
}

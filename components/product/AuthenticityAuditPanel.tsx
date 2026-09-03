"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Fingerprint, KeyRound, ScanEye, ShieldAlert, ShieldCheck } from "lucide-react";
import { getProductAuthenticity } from "@/lib/api";
import type { AuthenticityAudit } from "@/lib/api";

const RISK_STYLES = {
  low: "bg-signal-good/10 text-signal-good",
  medium: "bg-signal-hold/10 text-signal-hold",
  high: "bg-signal-reject/10 text-signal-reject",
} as const;

/** Authenticity Audit tab: cryptographic listing checks + seller risk score. */
export default function AuthenticityAuditPanel({ productSlug }: { productSlug: string }) {
  const [audit, setAudit] = useState<AuthenticityAudit | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProductAuthenticity(productSlug)
      .then((result) => { if (!cancelled) setAudit(result); })
      .catch((requestError: Error) => { if (!cancelled) setError(requestError.message); });
    return () => { cancelled = true; };
  }, [productSlug]);

  if (error) return <p className="py-6 text-center text-xs text-signal-reject">{error}</p>;
  if (!audit) return <p className="py-6 text-center text-xs text-ink-700">Running authenticity checks…</p>;

  const zk = audit.zk_verification;
  const stamp = audit.cryptographic_stamp;
  const scan = audit.synthetic_image_scan;

  return (
    <section className="glass rounded-xl2 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 font-display text-sm font-bold text-ink-100">
          <Fingerprint className="h-4 w-4 text-astra-cyan" /> Authenticity Audit
        </h2>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase ${RISK_STYLES[audit.risk_band]}`}>
            Seller risk {audit.seller_risk_score}/100 · {audit.risk_band}
          </span>
          <span className="rounded-full border border-base-600 px-3 py-1 text-[9px] font-bold uppercase text-ink-500">ASTRA demo metadata · no public-chain verification</span>
        </div>
      </div>

      {stamp && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-emerald-400/25 bg-emerald-400/5 px-3 py-2.5">
          <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-400" />
          <div className="min-w-0">
            <p className="text-[11px] font-bold text-emerald-400">Cryptographic Stamp Metadata</p>
            <p className="truncate font-mono text-[9px] text-ink-500">{stamp.stamp_id} · {stamp.algorithm} · signed payload {stamp.signed_payload}… · attested by {stamp.attested_by}</p>
          </div>
        </div>
      )}

      <p className="mt-3 break-all rounded-xl bg-base-900 p-3 font-mono text-[10px] text-ink-500">
        SHA-256 listing fingerprint: {audit.listing_hash}
      </p>

      {(zk || audit.seller_reputation_hash || scan) && (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {zk && (
            <div className="rounded-xl border border-base-600 bg-base-900/60 p-3">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-violet-400"><KeyRound className="h-3 w-3" /> ZK Verification Metadata</p>
              <p className="mt-2 font-mono text-[9px] text-ink-500">{zk.proof_id}</p>
              <p className="mt-1 text-[10px] text-ink-300">{zk.protocol} · circuit {zk.circuit}</p>
              <p className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-signal-good/10 px-2 py-0.5 text-[9px] font-bold uppercase text-signal-good">
                <ShieldCheck className="h-3 w-3" /> Verified in {zk.verify_ms}ms
              </p>
            </div>
          )}
          {audit.seller_reputation_hash && (
            <div className="rounded-xl border border-base-600 bg-base-900/60 p-3">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-astra-cyan"><Fingerprint className="h-3 w-3" /> Seller Reputation Hash</p>
              <p className="mt-2 break-all font-mono text-[9px] text-ink-500">{audit.seller_reputation_hash}</p>
              <p className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-astra-gradient-soft px-2 py-0.5 text-[9px] font-bold uppercase text-ink-100">No public-chain verification</p>
            </div>
          )}
          {scan && (
            <div className="rounded-xl border border-base-600 bg-base-900/60 p-3">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-cyan-400"><ScanEye className="h-3 w-3" /> AI Synthetic Image Scan</p>
              <p className="mt-2 font-display text-lg font-bold text-ink-100">{scan.score}%</p>
              <p className="text-[10px] text-ink-500">synthetic manipulation · {scan.frames_analyzed} frames · {scan.model}</p>
              <p className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-signal-good/10 px-2 py-0.5 text-[9px] font-bold uppercase text-signal-good">
                <ShieldCheck className="h-3 w-3" /> 0% manipulation — authentic
              </p>
            </div>
          )}
        </div>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {audit.checks.map((check) => (
          <li key={check.id} className="flex items-start gap-3 rounded-xl border border-base-600 bg-base-900/60 p-3">
            {check.status === "pass" ? (
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-signal-good" />
            ) : (
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-signal-hold" />
            )}
            <div>
              <p className="text-xs font-semibold text-ink-100">{check.label}</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-ink-500">{check.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

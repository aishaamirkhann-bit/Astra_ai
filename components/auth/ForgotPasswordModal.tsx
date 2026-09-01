"use client";

import { useState } from "react";
import { KeyRound, Loader2, X } from "lucide-react";
import { forgotPassword, resetPassword } from "@/lib/api";
import { showToast } from "@/lib/toast";
import PasswordInput from "@/components/auth/PasswordInput";

export default function ForgotPasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [stage, setStage] = useState<"request" | "reset">("request");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const requestCode = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await forgotPassword({ email });
      showToast(result.message, "info");
      setStage("reset");
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submitReset = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await resetPassword({ email, code, new_password: newPassword });
      showToast(result.message, "success");
      onClose();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/75 p-4 backdrop-blur-sm" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="glass w-full max-w-md rounded-3xl p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-violet-400">
              <KeyRound className="h-3 w-3" /> Password reset
            </p>
            <h2 className="mt-1 font-display text-lg font-bold text-ink-100">
              {stage === "request" ? "Email me code bhejein" : "Code + naya password"}
            </h2>
          </div>
          <button onClick={onClose} aria-label="Close reset dialog" className="rounded-full bg-base-800 p-2 text-ink-300 hover:text-ink-100">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 flex flex-col gap-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            disabled={stage === "reset"}
            className="w-full rounded-xl border border-base-600 bg-base-900 px-4 py-3 text-xs text-ink-100 disabled:opacity-60"
          />
          {stage === "reset" && (
            <>
              <input
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="6-digit code"
                className="w-full rounded-xl border border-base-600 bg-base-900 px-4 py-3 text-center font-mono text-sm tracking-[0.4em] text-ink-100"
              />
              <PasswordInput value={newPassword} onChange={setNewPassword} placeholder="Naya password (min 6 chars)" autoComplete="new-password" />
            </>
          )}
          {error && <p className="rounded-lg bg-signal-reject/10 px-3 py-2 text-xs font-medium text-signal-reject">{error}</p>}
          <button
            onClick={() => void (stage === "request" ? requestCode() : submitReset())}
            disabled={busy || !email || (stage === "reset" && (code.length !== 6 || newPassword.length < 6))}
            className="flex items-center justify-center gap-2 rounded-xl bg-astra-gradient py-3 text-xs font-bold text-white disabled:opacity-50"
          >
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {stage === "request" ? "Send reset code" : "Reset password"}
          </button>
        </div>
      </section>
    </div>
  );
}

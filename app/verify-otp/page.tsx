"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Loader2, ArrowRight, RotateCw } from "lucide-react";
import { verifyOtp, resendOtp } from "@/lib/api";
import { storeSession, getPendingOtp, storePendingOtp, clearPendingOtp, consumePostAuthRedirect } from "@/lib/auth";

const CODE_LENGTH = 6;

export default function VerifyOtpPage() {
  const router = useRouter();
  const [pending, setPending] = useState<ReturnType<typeof getPendingOtp>>(null);
  const [digits, setDigits] = useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const inputsRef = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    const p = getPendingOtp();
    if (!p) {
      // No OTP challenge in flight — nothing to verify, send them back.
      router.replace("/login");
      return;
    }
    setPending(p);
    inputsRef.current[0]?.focus();
  }, [router]);

  function handleDigitChange(index: number, value: string) {
    const clean = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = clean;
    setDigits(next);
    if (clean && index < CODE_LENGTH - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, CODE_LENGTH);
    if (!pasted) return;
    e.preventDefault();
    setDigits(Array.from({ length: CODE_LENGTH }, (_, i) => pasted[i] ?? ""));
    inputsRef.current[Math.min(pasted.length, CODE_LENGTH - 1)]?.focus();
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pending) return;
    const code = digits.join("");
    if (code.length !== CODE_LENGTH) {
      setError(`Please enter the full ${CODE_LENGTH}-digit code.`);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const session = await verifyOtp({ otp_token: pending.otp_token, code });
      storeSession(session);
      clearPendingOtp();
      router.replace(consumePostAuthRedirect());
      router.refresh();
    } catch {
      setError("Incorrect or expired code. Try again or resend.");
      setDigits(Array(CODE_LENGTH).fill(""));
      inputsRef.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!pending) return;
    setError(null);
    setInfo(null);
    setResending(true);
    try {
      const fresh = await resendOtp({ otp_token: pending.otp_token });
      storePendingOtp(fresh);
      setPending(fresh);
      setDigits(Array(CODE_LENGTH).fill(""));
      setInfo(`New code sent to ${fresh.email}.`);
      inputsRef.current[0]?.focus();
    } catch {
      setError("Could not resend code — please try logging in again.");
    } finally {
      setResending(false);
    }
  }

  if (!pending) return null;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-base-950 bg-astra-glow px-4 py-10">
      <div className="pointer-events-none absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-astra-indigo/20 blur-[100px]" />
      <div className="pointer-events-none absolute -bottom-32 right-1/4 h-72 w-72 rounded-full bg-astra-violet/20 blur-[100px]" />

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-astra-gradient shadow-glow">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink-100">Verify it&apos;s you</h1>
            <p className="mt-1 text-sm text-ink-500">
              Code bheja gaya hai <span className="text-ink-300">{pending.email}</span> par
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-xl2 p-6 sm:p-8">
          <div className="flex flex-col gap-5">
            <div className="flex justify-center gap-2">
              {digits.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => {
                    inputsRef.current[i] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleDigitChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  onPaste={handlePaste}
                  className="h-12 w-11 rounded-xl border border-base-600 bg-base-800/60 text-center text-lg font-semibold text-ink-100 focus:border-astra-violet focus:outline-none"
                />
              ))}
            </div>

            {error && (
              <p className="rounded-lg bg-signal-reject/10 px-3 py-2 text-center text-xs font-medium text-signal-reject">
                {error}
              </p>
            )}
            {info && !error && (
              <p className="rounded-lg bg-signal-good/10 px-3 py-2 text-center text-xs font-medium text-signal-good">
                {info}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex items-center justify-center gap-2 rounded-xl bg-astra-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
                <>
                  Verify & continue <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleResend}
              disabled={resending}
              className="flex items-center justify-center gap-1.5 text-xs font-medium text-ink-500 hover:text-ink-100 disabled:opacity-60"
            >
              {resending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
              Resend code
            </button>
          </div>
        </form>

        <p className="mt-6 text-center text-[11px] text-ink-500">
          Code {pending.expires_in_minutes} minutes mein expire ho jayega.
        </p>
      </div>
    </div>
  );
}

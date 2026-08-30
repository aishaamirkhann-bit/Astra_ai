"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShieldCheck, Mail, Lock, Loader2, ArrowRight } from "lucide-react";
import { loginUser } from "@/lib/api";
import { storePendingOtp, storePostAuthRedirect } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const otpChallenge = await loginUser({ email, password });
      storePendingOtp(otpChallenge);
      storePostAuthRedirect(new URLSearchParams(window.location.search).get("next") ?? "/");
      router.push("/verify-otp");
    } catch {
      setError("Invalid email or password. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-base-950 bg-astra-glow px-4 py-10">
      {/* Ambient orb accents, consistent with the rest of ASTRA */}
      <div className="pointer-events-none absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-astra-indigo/20 blur-[100px]" />
      <div className="pointer-events-none absolute -bottom-32 right-1/4 h-72 w-72 rounded-full bg-astra-violet/20 blur-[100px]" />

      <div className="relative w-full max-w-md">
        {/* Brand mark */}
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-astra-gradient shadow-glow">
            <ShieldCheck className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink-100">Welcome back</h1>
            <p className="mt-1 text-sm text-ink-500">Sign in to your ASTRA AI account</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-xl2 p-6 sm:p-8">
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-ink-300">Email</span>
              <div className="glass-hover flex items-center gap-2.5 rounded-xl border border-base-600 bg-base-800/60 px-3.5 py-2.5">
                <Mail className="h-4 w-4 shrink-0 text-ink-500" />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-ink-300">Password</span>
              <div className="glass-hover flex items-center gap-2.5 rounded-xl border border-base-600 bg-base-800/60 px-3.5 py-2.5">
                <Lock className="h-4 w-4 shrink-0 text-ink-500" />
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
                />
              </div>
            </label>

            {error && (
              <p className="rounded-lg bg-signal-reject/10 px-3 py-2 text-xs font-medium text-signal-reject">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-astra-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  Sign in <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>

        <p className="mt-6 text-center text-sm text-ink-500">
          Naya account? {" "}
          <Link href="/signup" className="font-medium text-astra-indigo hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}

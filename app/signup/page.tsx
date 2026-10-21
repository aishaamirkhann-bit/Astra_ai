"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ShieldCheck, Mail, User, Loader2, ArrowRight, ShoppingBag, Store } from "lucide-react";
import { registerUser } from "@/lib/api";
import { storePendingOtp } from "@/lib/auth";
import PasswordInput from "@/components/auth/PasswordInput";
import type { UserRole } from "@/lib/types";
import { COUNTRY_OPTIONS, getSavedCountry, saveCountry, type CountryCode } from "@/lib/region";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("buyer");
  const [country, setCountry] = useState<CountryCode>("PK");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const savedCountry = getSavedCountry();
    if (savedCountry) setCountry(savedCountry);
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (name.trim().length < 2) {
      setError("Please enter your full name (at least 2 characters).");
      return;
    }

    if (password.length < 6) {
      setError("Password kam se kam 6 characters ka hona chahiye.");
      return;
    }

    setLoading(true);
    try {
      const otpChallenge = await registerUser({ name: name.trim(), email: email.trim(), password, role, country });
      storePendingOtp(otpChallenge);
      router.push("/verify-otp");
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (message.toLowerCase().includes("already registered")) {
        setError("Yeh email pehle se registered hai. Sign in karein.");
      } else if (message.toLowerCase().includes("verification email")) {
        setError(`${message} Agar account pehle ban chuka hai to sign in karke code resend karein.`);
      } else {
        setError(message || "Account nahi ban saka. Dobara try karein.");
      }
    } finally {
      setLoading(false);
    }
  }

  function continueWithGoogle() {
    setError(null);
    setGoogleLoading(true);
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");
    const params = new URLSearchParams({ role, country });
    window.location.assign(`${apiUrl}/api/v1/auth/google/start?${params.toString()}`);
  }

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
            <h1 className="font-display text-2xl font-semibold text-ink-100">Create your account</h1>
            <p className="mt-1 text-sm text-ink-500">Join ASTRA AI — shop smarter, spend safer</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-xl2 p-6 sm:p-8">
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-ink-300">Full name</span>
              <div className="glass-hover flex items-center gap-2.5 rounded-xl border border-base-600 bg-base-800/60 px-3.5 py-2.5">
                <User className="h-4 w-4 shrink-0 text-ink-500" />
                <input
                  type="text"
                  required
                  minLength={2}
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full bg-transparent text-sm text-ink-100 placeholder:text-ink-500 focus:outline-none"
                />
              </div>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-ink-300">Country or region</span>
              <select value={country} onChange={(event) => { const selected = event.target.value as CountryCode; setCountry(selected); saveCountry(selected); }} className="w-full rounded-xl border border-base-600 bg-base-800 px-3.5 py-3 text-sm text-ink-100 outline-none focus:border-astra-violet">
                {COUNTRY_OPTIONS.map((option) => <option key={option.code} value={option.code} className="bg-base-900">{option.name}</option>)}
              </select>
            </label>

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
              <PasswordInput value={password} onChange={setPassword} placeholder="Kam se kam 6 characters" autoComplete="new-password" />
            </label>

            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-ink-300">Aap kya karna chahte hain?</span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setRole("buyer")}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border px-3 py-3 text-xs font-medium transition-colors ${
                    role === "buyer"
                      ? "border-astra-violet bg-astra-violet/10 text-ink-100"
                      : "border-base-600 bg-base-800/60 text-ink-500 hover:text-ink-100"
                  }`}
                >
                  <ShoppingBag className="h-4 w-4" />
                  Buyer
                </button>
                <button
                  type="button"
                  onClick={() => setRole("seller")}
                  className={`flex flex-col items-center gap-1.5 rounded-xl border px-3 py-3 text-xs font-medium transition-colors ${
                    role === "seller"
                      ? "border-astra-violet bg-astra-violet/10 text-ink-100"
                      : "border-base-600 bg-base-800/60 text-ink-500 hover:text-ink-100"
                  }`}
                >
                  <Store className="h-4 w-4" />
                  Seller
                </button>
              </div>
            </div>

            {error && (
              <p role="alert" aria-live="polite" className="rounded-lg bg-signal-reject/10 px-3 py-2 text-xs font-medium text-signal-reject">
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
                  Create account <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
            <div className="flex items-center gap-3 py-1 text-[10px] uppercase tracking-wide text-ink-700">
              <span className="h-px flex-1 bg-base-600" />
              <span>Or</span>
              <span className="h-px flex-1 bg-base-600" />
            </div>
            <button
              type="button"
              disabled={googleLoading}
              onClick={continueWithGoogle}
              className="flex items-center justify-center gap-2 rounded-xl border border-base-600 bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="grid h-5 w-5 place-items-center rounded-full bg-slate-800 text-xs font-bold text-white">G</span>
              {googleLoading ? "Redirecting…" : "Continue with Google"}
            </button>
            <p className="text-center text-[10px] text-ink-500">Without OAuth keys, development opens a clearly marked local demo account.</p>
          </div>
        </form>

        <p className="mt-6 text-center text-sm text-ink-500">
          Pehle se account hai? {" "}
          <Link href="/login" className="font-medium text-astra-indigo hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

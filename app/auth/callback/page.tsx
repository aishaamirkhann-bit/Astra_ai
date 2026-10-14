"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldCheck } from "lucide-react";
import { getCurrentUser } from "@/lib/api";
import { clearSession, storeUserProfile } from "@/lib/auth";
import { showToast } from "@/lib/toast";

export default function GoogleAuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void getCurrentUser().then((user) => {
      if (!active) return;
      storeUserProfile(user);
      showToast(`Welcome to ASTRA, ${user.name}`, "success");
      router.replace(user.role === "seller" ? "/seller/dashboard" : "/buyer/dashboard");
      router.refresh();
    }).catch(() => {
      if (!active) return;
      clearSession();
      setError("Google sign-in finished, but ASTRA could not load your account. Please try again.");
    });
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-base-950 bg-astra-glow px-4 py-10">
      <div className="pointer-events-none absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-astra-indigo/20 blur-[100px]" />
      <div className="pointer-events-none absolute -bottom-32 right-1/4 h-72 w-72 rounded-full bg-astra-violet/20 blur-[100px]" />
      <section className="glass relative w-full max-w-md rounded-xl2 p-8 text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-astra-gradient shadow-glow">
          <ShieldCheck className="h-6 w-6 text-white" />
        </div>
        {error ? (
          <>
            <h1 className="mt-5 font-display text-lg font-semibold text-ink-100">Sign-in needs another try</h1>
            <p role="alert" className="mt-2 text-sm text-signal-reject">{error}</p>
            <button
              type="button"
              onClick={() => router.replace("/login?oauth_error=session")}
              className="mt-5 rounded-xl bg-astra-gradient px-4 py-2.5 text-sm font-semibold text-white"
            >
              Return to sign in
            </button>
          </>
        ) : (
          <>
            <h1 className="mt-5 font-display text-lg font-semibold text-ink-100">Finishing Google sign-in</h1>
            <p className="mt-2 text-sm text-ink-500">Securely loading your ASTRA account…</p>
            <Loader2 className="mx-auto mt-5 h-5 w-5 animate-spin text-astra-cyan" />
          </>
        )}
      </section>
    </main>
  );
}

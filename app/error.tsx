"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";

export default function ErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <main className="grid min-h-screen place-items-center bg-base-950 p-6"><section className="glass w-full max-w-md rounded-3xl p-8 text-center"><AlertTriangle className="mx-auto h-10 w-10 text-amber-400" /><h1 className="mt-5 font-display text-xl font-bold text-ink-100">Astra hit a temporary snag</h1><p className="mt-2 text-sm text-ink-500">Your wallet and order state are safe. Retry the request without reloading the entire app.</p><button onClick={reset} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-astra-gradient px-5 py-3 text-sm font-bold text-white"><RotateCcw className="h-4 w-4" /> Try again</button></section></main>;
}

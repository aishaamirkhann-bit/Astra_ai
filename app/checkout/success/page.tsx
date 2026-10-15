"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getStripeCheckoutStatus } from "@/lib/api";

type CheckoutStatus = Awaited<ReturnType<typeof getStripeCheckoutStatus>>;

export default function CheckoutSuccessPage() {
  const [checkoutRef, setCheckoutRef] = useState("");
  const [status, setStatus] = useState<CheckoutStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setCheckoutRef(new URLSearchParams(window.location.search).get("checkout_ref") ?? "");
  }, []);

  useEffect(() => {
    if (!checkoutRef) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await getStripeCheckoutStatus(checkoutRef);
        if (!active) return;
        setStatus(result);
        if (["pending", "pending_payment"].includes(result.payment_status)) timer = setTimeout(refresh, 2000);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load order status");
      }
    };
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [checkoutRef]);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink-100">Payment status</h1>
      {error ? <p role="alert" className="mt-4 text-sm text-signal-reject">{error}</p> : null}
      {!checkoutRef ? <p className="mt-4 text-sm text-ink-500">Checkout reference is missing.</p> : null}
      {status ? (
        <section className="mt-5 border-l-2 border-emerald-400 pl-4">
          <p className="text-sm text-ink-100">Payment: {status.payment_status.replaceAll("_", " ")}</p>
          <p className="mt-1 text-sm text-ink-500">Order: {status.checkout_status.replaceAll("_", " ")}</p>
          {status.order_refs.map((orderRef) => <p key={orderRef} className="mt-2 font-mono text-xs text-ink-300">{orderRef}</p>)}
        </section>
      ) : !error && checkoutRef ? <p className="mt-4 text-sm text-ink-500">Checking with ASTRA…</p> : null}
      <Link href="/orders" className="mt-8 w-fit text-sm font-semibold text-ink-100 underline">View orders</Link>
    </main>
  );
}
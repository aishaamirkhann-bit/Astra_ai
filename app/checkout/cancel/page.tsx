"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cancelStripeCheckout, getStripeCheckoutStatus } from "@/lib/api";

export default function CheckoutCancelPage() {
  const [checkoutRef, setCheckoutRef] = useState("");
  const [message, setMessage] = useState("Releasing reserved items…");

  useEffect(() => {
    setCheckoutRef(new URLSearchParams(window.location.search).get("checkout_ref") ?? "");
  }, []);

  useEffect(() => {
    if (!checkoutRef) { setMessage("Checkout reference is missing."); return; }
    void cancelStripeCheckout(checkoutRef)
      .then(async (result) => {
        const orderStatus = await getStripeCheckoutStatus(checkoutRef);
        setMessage(result.payment_status === "paid"
          ? `Payment ${orderStatus.payment_status.replaceAll("_", " ")}; order ${orderStatus.checkout_status.replaceAll("_", " ")}.`
          : `Checkout ${orderStatus.checkout_status.replaceAll("_", " ")}. Reserved items were returned to your cart.`);
      })
      .catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : "Could not update checkout status."));
  }, [checkoutRef]);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink-100">Checkout cancelled</h1>
      <p className="mt-4 text-sm text-ink-500">{message}</p>
      <Link href="/explore" className="mt-8 w-fit text-sm font-semibold text-ink-100 underline">Return to shopping</Link>
    </main>
  );
}
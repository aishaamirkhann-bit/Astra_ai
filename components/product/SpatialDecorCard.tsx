"use client";

import { createElement, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import Script from "next/script";
import { Camera, Loader2, Sofa } from "lucide-react";
import { getSpatialDecorRecommendations, type SpatialDecorRecommendations } from "@/lib/api";
import { getSavedLocale } from "@/lib/region";

const MODEL_VIEWER_SCRIPT = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.4.0/model-viewer.min.js";

function activeLocale(): string {
  return getSavedLocale();
}

export default function SpatialDecorCard() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<SpatialDecorRecommendations | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [arProduct, setArProduct] = useState<string | null>(null);

  async function recommend() {
    if (!photo) { setError("Choose a room photo to get spatial decor suggestions."); return; }
    setBusy(true); setError("");
    try { setResult(await getSpatialDecorRecommendations(photo, message, activeLocale())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Room suggestions are unavailable right now."); }
    finally { setBusy(false); }
  }

  const currentItem = result?.items.find((item) => item.product.id === arProduct);
  const modelUrl = currentItem?.product.model_url;

  return <section className="glass mt-6 rounded-2xl p-5" aria-labelledby="spatial-decor-title">
    {arProduct && modelUrl && <Script src={MODEL_VIEWER_SCRIPT} strategy="afterInteractive" />}
    <header className="flex items-start gap-3"><span className="rounded-xl bg-emerald-400/10 p-2 text-emerald-300"><Sofa className="h-5 w-5" /></span><div><h2 id="spatial-decor-title" className="font-display text-base font-bold text-white">Spatial Room Decorator</h2><p className="mt-1 text-xs text-ink-400">Upload a room photo for advisory furniture and decor matches.</p></div></header>
    <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
      <label className="rounded-xl border border-base-600 bg-base-900 px-3 py-2 text-xs text-ink-300">Room photo<input className="mt-2 block w-full text-[11px]" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} /></label>
      <input value={message} onChange={(event) => setMessage(event.target.value)} maxLength={1000} placeholder="Style, colors, or arrangement you prefer" className="rounded-xl border border-base-600 bg-base-900 px-3 py-2 text-xs text-white" />
      <button type="button" onClick={() => void recommend()} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-3 text-xs font-bold text-white hover:bg-emerald-600 disabled:opacity-60">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />} Find decor</button>
    </div>
    {error && <p role="alert" className="mt-3 text-xs text-rose-300">{error}</p>}
    {result && <div className="mt-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{result.items.map(({ slot, product, match_reason, cross_border_advisory }) => <article key={product.id} className="overflow-hidden rounded-xl border border-base-700 bg-base-900">
        <div className="relative h-36 bg-base-800"><Image src={product.image_url} alt={product.title} fill unoptimized className="object-cover" /></div>
        <div className="p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-emerald-300">{slot}</p><Link href={`/product/${encodeURIComponent(product.id)}`} className="mt-1 block text-xs font-semibold text-white hover:underline">{product.title}</Link><p className="mt-1 text-[10px] text-ink-400">{match_reason}</p>{cross_border_advisory && <p className="mt-2 text-[10px] text-amber-300">{cross_border_advisory.message}</p>}
          <button type="button" disabled={!product.model_url} onClick={() => setArProduct(product.id)} title={!product.model_url ? "This listing has no seller-provided 3D model" : undefined} className="mt-3 rounded-lg border border-emerald-500/50 px-3 py-2 text-[10px] font-semibold text-emerald-200 enabled:hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:opacity-50">View in Your Room (AR)</button>
        </div>
      </article>)}</div>
      <p className="mt-4 text-xs text-ink-300">Estimated listed total: Rs. {result.estimated_bundle_total.toLocaleString("en-PK")}</p>
      <p className="mt-1 text-[10px] text-ink-500">{result.dimension_note} {result.message}</p>
      {Object.values(result.room_attributes).some(Boolean) && <details className="mt-3 text-[10px] text-ink-400"><summary className="cursor-pointer">Room photo observations</summary><dl className="mt-2 grid gap-1">{Object.entries(result.room_attributes).map(([key, value]) => value && <div key={key}><dt className="inline font-semibold">{key.replaceAll("_", " ")}: </dt><dd className="inline">{value}</dd></div>)}</dl></details>}
    </div>}
    {arProduct && <div role="dialog" aria-modal="true" className="fixed inset-0 z-[120] grid place-items-center bg-slate-950/80 p-4"><section className="w-full max-w-lg rounded-2xl bg-base-900 p-5"><div className="flex justify-between"><h3 className="font-semibold text-white">Room placement preview</h3><button onClick={() => setArProduct(null)} className="text-xs text-ink-300">Close</button></div>{modelUrl ? createElement("model-viewer", { src: modelUrl, alt: currentItem?.product.title ?? "3D product model", "camera-controls": "", ar: "", "ar-modes": "webxr scene-viewer quick-look", style: { width: "100%", height: "min(55vh, 420px)" } }, createElement("button", { slot: "ar-button", className: "rounded-lg bg-violet-600 px-4 py-2 text-xs text-white" }, "Place in your room")) : <p className="mt-3 text-xs text-ink-400">This listing has no supported 3D model.</p>}<p className="mt-3 text-[10px] text-ink-500">Preview only; it does not add items to cart or change checkout.</p></section></div>}
    <p className="mt-4 text-[10px] text-ink-500">Suggestions are read-only. Confirm dimensions and review items before using the regular cart and consent checkout.</p>
  </section>;
}

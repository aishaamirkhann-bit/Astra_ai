"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { Camera, Rotate3D, X } from "lucide-react";
import type { ProductDetail } from "@/lib/types";
import { getARModelForProduct } from "@/lib/arIntent";

const MODEL_VIEWER_SCRIPT = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.4.0/model-viewer.min.js";

export default function ARTryOnModal({ product, onClose }: { product: ProductDetail; onClose: () => void }) {
  const model = getARModelForProduct(product);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [viewerReady, setViewerReady] = useState(false);
  const [viewerError, setViewerError] = useState(false);
  const [scriptFailed, setScriptFailed] = useState(false);
  const [arMessage, setArMessage] = useState("");
  const [exposure, setExposure] = useState(1);

  useEffect(() => {
    const viewerHost = hostRef.current;
    if (!viewerReady || !model || !viewerHost || typeof document === "undefined") return;
    const viewer = document.createElement("model-viewer");
    viewer.setAttribute("src", model.src);
    viewer.setAttribute("alt", `${model.label} for ${product.name}`);
    viewer.setAttribute("camera-controls", "");
    viewer.setAttribute("touch-action", "pan-y");
    viewer.setAttribute("auto-rotate", "");
    viewer.setAttribute("ar", "");
    viewer.setAttribute("ar-modes", "webxr scene-viewer quick-look");
    viewer.setAttribute("shadow-intensity", "1");
    viewer.style.width = "100%";
    viewer.style.height = "min(55vh, 440px)";
    viewer.style.background = "#101827";
    viewer.addEventListener("error", () => setViewerError(true), { once: true });
    viewer.addEventListener("ar-status", (event) => {
      const status = (event as CustomEvent<{ status?: string }>).detail?.status;
      if (status === "failed") setArMessage("AR could not start. Check camera permissions and device support; the 3D preview remains available.");
      if (status === "not-presenting") setArMessage("");
    });

    // model-viewer only requests camera/AR capabilities after the buyer taps
    // this explicit slotted control. Loading and rotating the model is local.
    const arButton = document.createElement("button");
    arButton.slot = "ar-button";
    arButton.type = "button";
    arButton.className = "rounded-full bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-lg";
    arButton.textContent = "View in your space";
    viewer.append(arButton);
    viewerHost.replaceChildren(viewer);
    return () => { viewerHost.replaceChildren(); };
  }, [model, product.name, viewerReady]);

  useEffect(() => {
    hostRef.current?.querySelector("model-viewer")?.setAttribute("exposure", String(exposure));
  }, [exposure]);

  return (
    <div className="fixed inset-0 z-[100] grid place-items-center bg-slate-950/80 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      {model && <Script src={MODEL_VIEWER_SCRIPT} strategy="afterInteractive" onReady={() => setViewerReady(true)} onError={() => setScriptFailed(true)} />}
      <section role="dialog" aria-modal="true" aria-labelledby="ar-preview-title" className="glass w-full max-w-2xl rounded-3xl border border-base-600 p-5 shadow-2xl">
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-astra-cyan"><Rotate3D className="h-4 w-4" /> Interactive preview</p>
            <h2 id="ar-preview-title" className="mt-1 font-display text-lg font-bold text-ink-100">{product.name}</h2>
          </div>
          <button type="button" aria-label="Close AR preview" onClick={onClose} className="rounded-full bg-base-800 p-2 text-ink-300 hover:text-white"><X className="h-4 w-4" /></button>
        </header>

        {!model ? (
          <div className="mt-5 rounded-2xl border border-base-600 bg-base-900/70 p-8 text-center">
            <Rotate3D className="mx-auto h-8 w-8 text-ink-500" />
            <p className="mt-3 text-sm font-semibold text-ink-100">3D preview is not available for this listing yet</p>
            <p className="mt-1 text-xs text-ink-500">This product has no seller-provided 3D model. The product page and your cart are unchanged.</p>
          </div>
        ) : viewerError || scriptFailed ? (
          <div role="status" className="mt-5 rounded-2xl border border-base-600 bg-base-900/70 p-8 text-center text-xs text-ink-400">The 3D viewer could not load. Try again later; no product or checkout state was changed.</div>
        ) : (
          <>
            <div ref={hostRef} className="mt-4 min-h-48 overflow-hidden rounded-2xl bg-base-900" aria-label="Interactive 3D model viewer">
              {!viewerReady && <p className="p-12 text-center text-xs text-ink-500">Loading the 3D viewer…</p>}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-[11px] text-ink-400">Lighting
                <input aria-label="Adjust model lighting" type="range" min="0.5" max="2" step="0.1" value={exposure} onChange={(event) => setExposure(Number(event.target.value))} />
              </label>
              <span className="inline-flex items-center gap-1 text-[10px] text-ink-500"><Camera className="h-3 w-3" /> Camera is requested only after you choose “View in your space” on a supported device.</span>
            </div>
            {arMessage && <p role="status" className="mt-2 text-xs text-signal-hold">{arMessage}</p>}
            {model.illustrative && <p className="mt-3 text-[10px] text-signal-hold">Illustrative sample only — this is not the exact catalog garment or a fit/size simulation.</p>}
          </>
        )}
        <p className="mt-4 text-[10px] text-ink-500">Preview only. Opening or using AR does not add to cart, place an order, or authorize spending.</p>
      </section>
    </div>
  );
}

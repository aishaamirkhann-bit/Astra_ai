"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import type { ToastTone } from "@/lib/toast";

type Toast = { id: number; message: string; tone: ToastTone };

const TONE_META: Record<ToastTone, { icon: typeof Info; className: string }> = {
  error: { icon: XCircle, className: "border-signal-reject/40 bg-signal-reject/15 text-signal-reject" },
  success: { icon: CheckCircle2, className: "border-signal-good/40 bg-signal-good/15 text-signal-good" },
  info: { icon: Info, className: "border-astra-violet/40 bg-astra-gradient-soft text-ink-100" },
};

export default function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const push = (event: Event) => {
      const detail = (event as CustomEvent<{ message: string; tone: ToastTone }>).detail;
      const id = Date.now() + Math.random();
      setToasts((current) => [...current.slice(-3), { id, message: detail.message, tone: detail.tone }]);
      window.setTimeout(() => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
      }, 4200);
    };
    window.addEventListener("astra:toast", push);
    return () => window.removeEventListener("astra:toast", push);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-24 right-5 z-[95] flex w-72 flex-col gap-2">
      {toasts.map((toast) => {
        const meta = TONE_META[toast.tone];
        const Icon = meta.icon;
        return (
          <div key={toast.id} className={`flex items-start gap-2 rounded-xl border px-3 py-2.5 text-xs shadow-glow backdrop-blur ${meta.className}`}>
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p className="leading-relaxed">{toast.message}</p>
          </div>
        );
      })}
    </div>
  );
}

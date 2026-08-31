export type ToastTone = "error" | "success" | "info";

export function showToast(message: string, tone: ToastTone = "info") {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("astra:toast", { detail: { message, tone } }));
}

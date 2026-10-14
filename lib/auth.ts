// The JWT is intentionally inaccessible to JavaScript and lives only in the
// HTTP-only astra_token cookie. Only non-sensitive profile data is cached here.

import type { LoginResponse, UserRole } from "@/lib/types";

export type AccountMode = "buyer" | "seller";

const USER_KEY = "astra_user";
const ACCOUNT_MODE_KEY = "astra_account_mode";
export const ACCOUNT_MODE_EVENT = "astra:account-mode-change";
// Holds the short-lived otp_token between "password submitted" and
// "code verified" — cleared as soon as verification succeeds or fails.
const OTP_PENDING_KEY = "astra_otp_pending";
const POST_AUTH_REDIRECT_KEY = "astra_post_auth_redirect";

export function getStoredUser(): LoginResponse["user"] | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LoginResponse["user"];
  } catch {
    return null;
  }
}

export function getUserRole(): UserRole | null {
  return getStoredUser()?.role ?? null;
}

export function storeAccountMode(mode: AccountMode) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCOUNT_MODE_KEY, mode);
  window.dispatchEvent(new CustomEvent(ACCOUNT_MODE_EVENT, { detail: { mode } }));
}

export function getAccountMode(): AccountMode {
  if (typeof window === "undefined") return "buyer";
  const mode = window.localStorage.getItem(ACCOUNT_MODE_KEY);
  return mode === "seller" ? "seller" : "buyer";
}

export function clearAccountMode() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCOUNT_MODE_KEY);
  window.dispatchEvent(new CustomEvent(ACCOUNT_MODE_EVENT, { detail: { mode: "buyer" } }));
}

export function storeUserProfile(user: LoginResponse["user"]) {
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  storeAccountMode(user.role);
}

/** Called right after a successful /auth/verify-otp response. */
export function storeSession(session: LoginResponse) {
  storeUserProfile(session.user);
}

export function clearSession() {
  window.localStorage.removeItem(USER_KEY);
  clearAccountMode();
}

export function isLoggedIn(): boolean {
  return getStoredUser() !== null;
}

// --- Pending OTP challenge (between login/register and verify-otp) ---

export interface PendingOtp {
  otp_token: string;
  email: string;
  expires_in_minutes: number;
  message?: string;
}

export function storePendingOtp(pending: PendingOtp) {
  window.sessionStorage.setItem(OTP_PENDING_KEY, JSON.stringify(pending));
}

export function getPendingOtp(): PendingOtp | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(OTP_PENDING_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingOtp;
  } catch {
    return null;
  }
}

export function clearPendingOtp() {
  window.sessionStorage.removeItem(OTP_PENDING_KEY);
}

export function storePostAuthRedirect(path: string) {
  const safePath = path.startsWith("/") && !path.startsWith("//") ? path : "/";
  window.sessionStorage.setItem(POST_AUTH_REDIRECT_KEY, safePath);
}

export function consumePostAuthRedirect(fallback = "/"): string {
  const path = window.sessionStorage.getItem(POST_AUTH_REDIRECT_KEY) ?? fallback;
  window.sessionStorage.removeItem(POST_AUTH_REDIRECT_KEY);
  return path.startsWith("/") && !path.startsWith("//") ? path : "/";
}

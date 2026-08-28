// Small client-side helper around the JWT issued by /auth/verify-otp.
// Kept in one place so api.ts (server + client calls) and the UI (TopBar,
// login/signup pages) all agree on where the token lives.

import type { LoginResponse, UserRole } from "@/lib/types";

const TOKEN_KEY = "astra_token";
const USER_KEY = "astra_user";
// Holds the short-lived otp_token between "password submitted" and
// "code verified" — cleared as soon as verification succeeds or fails.
const OTP_PENDING_KEY = "astra_otp_pending";

/** Safe on the server too — returns null during SSR/server-component calls. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

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

/** Called right after a successful /auth/verify-otp response. */
export function storeSession(session: LoginResponse) {
  window.localStorage.setItem(TOKEN_KEY, session.access_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return getToken() !== null;
}

// --- Pending OTP challenge (between login/register and verify-otp) ---

export interface PendingOtp {
  otp_token: string;
  email: string;
  expires_in_minutes: number;
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

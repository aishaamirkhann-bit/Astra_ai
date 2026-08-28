import type {
  HomePageOut,
  ApprovalActionResponse,
  LoginResponse,
  OtpRequiredResponse,
  GoalOut,
  GoalCreatePayload,
  WalletDetailOut,
  WalletOut,
  UserRole,
  DealOut,
  DealDetail,
  DealListResponse,
  DealReservationResponse,
} from "@/lib/types";
import { getToken } from "@/lib/auth";

// Set in .env.local — see lib/api.ts usage below.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * NOTE on auth: the backend's get_current_user has a dev-mode fallback —
 * if no Bearer token is sent, it returns the seeded demo user ("Aisha").
 * That fallback still exists for pages that don't need real auth (Home,
 * etc). Once a token is present (post login/signup, see lib/auth.ts) it
 * gets attached automatically below.
 */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    // Home page data changes often (countdown, wallet, approval state) —
    // don't let Next.js cache this across requests.
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${body}`);
  }

  // 204 No Content (goal delete) has no body to parse.
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth — register/login now return an OTP challenge instead of a session.
// Complete the flow with verifyOtp() to get the real access token.
// ---------------------------------------------------------------------------

/** Sign-up page's form submit. Creates the (unverified) user + sends OTP. */
export function registerUser(payload: {
  name: string;
  email: string;
  password: string;
  role: UserRole;
  preferred_language?: string;
}): Promise<OtpRequiredResponse> {
  return apiFetch<OtpRequiredResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Sign-in page's form submit. Checks the password + sends OTP. */
export function loginUser(payload: { email: string; password: string }): Promise<OtpRequiredResponse> {
  return apiFetch<OtpRequiredResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** OTP entry screen's submit — completes login/register and returns the real session. */
export function verifyOtp(payload: { otp_token: string; code: string }): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** "Resend code" link on the OTP screen. */
export function resendOtp(payload: { otp_token: string }): Promise<OtpRequiredResponse> {
  return apiFetch<OtpRequiredResponse>("/auth/resend-otp", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Single call that hydrates the entire Home page in one round-trip. */
export function getHomePage(): Promise<HomePageOut> {
  return apiFetch<HomePageOut>("/home");
}

/** Promoted listings shown on the Deals page. */
export function getDeals(): Promise<DealOut[]> {
  return apiFetch<DealListResponse>("/deals?sort_by=highest_discount&page=1&page_size=100").then((response) => response.items);
}

export function getDealDetails(dealId: string): Promise<DealDetail> {
  return apiFetch<DealDetail>(`/deals/${dealId}/details`);
}

export function reserveDeal(
  dealId: string,
  selection: { quantity: number; size?: string; color?: string },
): Promise<DealReservationResponse> {
  return apiFetch<DealReservationResponse>(`/deals/${dealId}/reserve`, {
    method: "POST",
    body: JSON.stringify(selection),
  });
}

export function getDealsWebSocketUrl(): string {
  return `${API_URL.replace(/^http/, "ws")}/ws/deals`;
}

/** HumanApprovalWidget's "Approve Transaction" button. */
export function approveOrder(orderRef: string): Promise<ApprovalActionResponse> {
  return apiFetch<ApprovalActionResponse>("/approval/approve", {
    method: "POST",
    body: JSON.stringify({ order_ref: orderRef }),
  });
}

/** HumanApprovalWidget's "Cancel & Refund" button. */
export function cancelOrder(orderRef: string): Promise<ApprovalActionResponse> {
  return apiFetch<ApprovalActionResponse>("/approval/cancel", {
    method: "POST",
    body: JSON.stringify({ order_ref: orderRef }),
  });
}

/** AiAssistantWidget's "Add to Cart" button. */
export function addToCart(productSlug: string, quantity = 1): Promise<{ message: string; quantity: number }> {
  return apiFetch<{ message: string; quantity: number }>("/ai-assistant/add-to-cart", {
    method: "POST",
    body: JSON.stringify({ product_slug: productSlug, quantity }),
  });
}

// ---------------------------------------------------------------------------
// Goals — full CRUD, powers GoalManager.tsx on the /goals page.
// ---------------------------------------------------------------------------

export function getGoals(): Promise<GoalOut[]> {
  return apiFetch<GoalOut[]>("/goals");
}

export function createGoal(payload: GoalCreatePayload): Promise<GoalOut> {
  return apiFetch<GoalOut>("/goals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateGoal(goalId: number, payload: Partial<GoalCreatePayload>): Promise<GoalOut> {
  return apiFetch<GoalOut>(`/goals/${goalId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteGoal(goalId: number): Promise<void> {
  return apiFetch<void>(`/goals/${goalId}`, { method: "DELETE" });
}

/** Moves money from the wallet's free balance into a goal's saved amount. */
export function allocateToGoal(goalId: number, amount: number): Promise<GoalOut> {
  return apiFetch<GoalOut>(`/goals/${goalId}/allocate`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

// ---------------------------------------------------------------------------
// Wallet — powers the /wallet page.
// ---------------------------------------------------------------------------

export function getWallet(): Promise<WalletDetailOut> {
  return apiFetch<WalletDetailOut>("/wallet");
}

export function getWalletSummary(): Promise<WalletOut> {
  return apiFetch<WalletOut>("/wallet/summary");
}

export function topUpWallet(amount: number, label = "Wallet top-up"): Promise<WalletDetailOut> {
  return apiFetch<WalletDetailOut>("/wallet/topup", {
    method: "POST",
    body: JSON.stringify({ amount, label }),
  });
}

export function withdrawFromWallet(amount: number, label = "Wallet withdrawal"): Promise<WalletDetailOut> {
  return apiFetch<WalletDetailOut>("/wallet/withdraw", {
    method: "POST",
    body: JSON.stringify({ amount, label }),
  });
}

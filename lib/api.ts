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
  AddToCartResponse,
  OrderOut,
  AstraCheckDashboardStats,
  TrustActionResponse,
  TrustInspection,
  BudgetDashboardOut,
  MatchedDealOut,
  ShoppingGoalOut,
  ConsentAuthorizationResponse,
  OrderDetail,
  NotificationList,
  ProductDetail,
  Cart,
  CartCheckout,
  ChatConversation,
  AuditEntry,
  B2bEvaluation,
} from "@/lib/types";
// Set in .env.local — see lib/api.ts usage below.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit, cookieHeader?: string): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      ...init?.headers,
    },
    // Home page data changes often (countdown, wallet, approval state) —
    // don't let Next.js cache this across requests.
    cache: "no-store",
    credentials: "include",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string | Array<{ msg?: string }> };
      detail = typeof parsed.detail === "string" ? parsed.detail : Array.isArray(parsed.detail) ? parsed.detail.map((item) => item.msg).filter(Boolean).join(", ") : body;
    } catch {
      // Keep a plain-text server response when it is not JSON.
    }
    throw new Error(detail || `Request failed with status ${res.status}`);
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
export function getHomePage(cookieHeader?: string): Promise<HomePageOut> {
  return apiFetch<HomePageOut>("/home", undefined, cookieHeader);
}

export function getExploreData(cookieHeader?: string): Promise<{ available_balance: number }> {
  return apiFetch<{ available_balance: number }>("/explore/wallet", undefined, cookieHeader);
}

export function getCurrentUser(cookieHeader?: string): Promise<LoginResponse["user"]> { return apiFetch("/auth/me", undefined, cookieHeader); }
export function logoutUser(): Promise<void> { return apiFetch<void>("/auth/logout", { method: "POST" }); }

export function getAstraCheckDashboardStats(): Promise<AstraCheckDashboardStats> {
  return apiFetch<AstraCheckDashboardStats>("/astra-check/stats");
}

export function inspectTrust(query: string): Promise<TrustInspection> {
  return apiFetch<TrustInspection>("/astra-check/inspect", { method: "POST", body: JSON.stringify({ query }) });
}

export function applyTrustAction(
  action: "manual_override" | "flagged" | "approved_for_deals",
  payload: { product_id: string; reason: string; score?: number },
): Promise<TrustActionResponse> {
  const path = action === "manual_override" ? "/astra-check/override" : `/astra-check/actions/${action}`;
  return apiFetch<TrustActionResponse>(path, { method: "POST", body: JSON.stringify(payload) });
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
export function approveOrder(orderRef: string, consentId?: string): Promise<ApprovalActionResponse> {
  return apiFetch<ApprovalActionResponse>("/approval/approve", {
    method: "POST",
    body: JSON.stringify({ order_ref: orderRef, consent_id: consentId }),
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
export function addToCart(
  productSlug: string,
  quantity = 1,
  selection: { size?: string; color?: string; storage?: string } = {},
): Promise<AddToCartResponse> {
  return apiFetch<AddToCartResponse>("/cart/add", {
    method: "POST",
    body: JSON.stringify({ product_slug: productSlug, quantity, ...selection }),
  });
}

export function getProduct(slug: string, cookieHeader?: string): Promise<ProductDetail> { return apiFetch<ProductDetail>(`/products/${slug}`, undefined, cookieHeader); }
export function getCart(cookieHeader?: string): Promise<Cart> { return apiFetch<Cart>("/cart", undefined, cookieHeader); }
export function updateCartItem(itemId: number, quantity: number): Promise<Cart> { return apiFetch<Cart>(`/cart/${itemId}`, { method: "PUT", body: JSON.stringify({ quantity }) }); }
export function removeCartItem(itemId: number): Promise<Cart> { return apiFetch<Cart>(`/cart/${itemId}`, { method: "DELETE" }); }
export function checkoutCart(payload: { shipping_address: string; consent_id?: string }): Promise<CartCheckout> { return apiFetch<CartCheckout>("/cart/checkout", { method: "POST", body: JSON.stringify(payload) }); }
export function getChatHistory(): Promise<ChatConversation[]> { return apiFetch<ChatConversation[]>("/chat/history"); }
export function streamChat(payload: { message: string; conversation_id?: number }): Promise<Response> { return fetch(`${API_URL}/api/v1/chat/stream`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }

export function authorizeFinancialConsent(payload: { amount: number; auth_method: "Voice" | "OTP"; order_ref: string; voice_transcript?: string; consent_id?: string; otp_code?: string }): Promise<ConsentAuthorizationResponse> {
  return apiFetch<ConsentAuthorizationResponse>("/wallet/authorize-consent", { method: "POST", body: JSON.stringify(payload) });
}

export function getWalletWebSocketUrl(userId: number): string {
  return `${API_URL.replace(/^http/, "ws")}/ws/wallet/${userId}`;
}

export function getOrders(cookieHeader?: string): Promise<OrderOut[]> {
  return apiFetch<OrderOut[]>("/orders", undefined, cookieHeader);
}

export function getOrderDetail(orderRef: string): Promise<OrderDetail> { return apiFetch<OrderDetail>(`/orders/${orderRef}`); }
export function reorderItem(orderRef: string): Promise<{ order_ref: string; cart_total_quantity: number; message: string }> { return apiFetch(`/orders/${orderRef}/reorder`, { method: "POST" }); }
export function getOrdersAudit(cookieHeader?: string): Promise<AuditEntry[]> { return apiFetch<AuditEntry[]>("/orders/audit", undefined, cookieHeader); }

/** B2B Adapter playground — real deterministic verdict from the backend. */
export function evaluateB2bPayload(payload: Record<string, unknown>): Promise<B2bEvaluation> {
  return apiFetch<B2bEvaluation>("/b2b/evaluate", { method: "POST", body: JSON.stringify(payload) });
}

export function getNotifications(): Promise<NotificationList> { return apiFetch<NotificationList>("/notifications"); }
export function markNotificationRead(id: string): Promise<void> { return apiFetch<void>(`/notifications/${id}/read`, { method: "POST" }); }
export function clearNotifications(): Promise<void> { return apiFetch<void>("/notifications", { method: "DELETE" }); }
export function getNotificationsWebSocketUrl(): string { return `${API_URL.replace(/^http/, "ws")}/ws/notifications`; }
export function getOrdersWebSocketUrl(): string { return `${API_URL.replace(/^http/, "ws")}/ws/orders`; }

export function reverseOrder(orderRef: string): Promise<{ order_ref: string; status: "cancelled"; message: string }> {
  return apiFetch<{ order_ref: string; status: "cancelled"; message: string }>(`/orders/${orderRef}/reverse`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Goals — full CRUD, powers GoalManager.tsx on the /goals page.
// ---------------------------------------------------------------------------

export function getGoals(): Promise<GoalOut[]> {
  return apiFetch<GoalOut[]>("/goals");
}

export function getBudgetDashboard(cookieHeader?: string): Promise<BudgetDashboardOut> {
  return apiFetch<BudgetDashboardOut>("/goals/budget", undefined, cookieHeader);
}

export function createShoppingGoal(payload: { target_title: string; target_price: number; category: string; priority_level: "Low" | "Medium" | "High"; deadline?: string | null }): Promise<ShoppingGoalOut> {
  return apiFetch<ShoppingGoalOut>("/goals/create", { method: "POST", body: JSON.stringify(payload) });
}

export function updateShoppingGoal(goalId: number, payload: { target_price?: number; deposit_amount?: number; status?: "Active" | "Completed" | "Paused"; priority_level?: "Low" | "Medium" | "High"; deadline?: string | null }): Promise<ShoppingGoalOut> {
  return apiFetch<ShoppingGoalOut>(`/goals/${goalId}/update`, { method: "PUT", body: JSON.stringify(payload) });
}

export function getMatchedDeals(cookieHeader?: string): Promise<MatchedDealOut[]> {
  return apiFetch<MatchedDealOut[]>("/goals/matched-deals", undefined, cookieHeader);
}

export function updateMonthlyBudget(payload: { monthly_limit: number; current_spent?: number; rollover_savings?: number }): Promise<BudgetDashboardOut> {
  return apiFetch<BudgetDashboardOut>("/goals/budget", { method: "PUT", body: JSON.stringify(payload) });
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

export function getWallet(cookieHeader?: string): Promise<WalletDetailOut> {
  return apiFetch<WalletDetailOut>("/wallet", undefined, cookieHeader);
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

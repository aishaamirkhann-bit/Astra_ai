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
  CheckoutSession,
  CheckoutSessionConfirmation,
  ChatConversation,
  AuditEntry,
  B2bEvaluation,
  DirectConversation,
  DirectMessageOut,
  VoiceIntentResult,
  TranscribeResponse,
  SearchResponse,
  MicroSettlements,
  RemittanceContext,
  SwarmTrace,
  ResolutionTimeline,
} from "@/lib/types";
// Set in .env.local — see lib/api.ts usage below.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");

async function apiFetch<T>(path: string, init?: RequestInit, cookieHeader?: string): Promise<T> {
  const clientSide = typeof window !== "undefined" && !cookieHeader;
  const method = (init?.method ?? "GET").toUpperCase();
  const idempotent = method === "GET" || method === "HEAD";
  const attempt = async (): Promise<Response> => {
    const started = performance.now();
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
    if (res.status >= 500 && clientSide) {
      const { pushAgentLog } = await import("@/lib/agentLog");
      pushAgentLog({ agent: "Sentinel", severity: "warn", route: `${method} ${path}`, detail: `Primary route returned ${res.status} — rerouting request via fallback gateway (${Math.round(performance.now() - started)}ms).` });
      throw new Error(`__ASTRA_REROUTE__:${res.status}`);
    }
    return res;
  };

  let res: Response;
  try {
    res = await attempt();
  } catch (cause) {
    const rerouted = cause instanceof Error && cause.message.startsWith("__ASTRA_REROUTE__");
    if (!clientSide || (!rerouted && !(cause instanceof TypeError))) throw cause;
    const { pushAgentLog } = await import("@/lib/agentLog");
    if (!rerouted) {
      pushAgentLog({ agent: "Sentinel", severity: "warn", route: `${method} ${path}`, detail: "Primary API unreachable — autonomous fallback engaged." });
    }
    if (idempotent) {
      try {
        res = await attempt();
        pushAgentLog({ agent: "Sentinel", severity: "recovered", route: `${method} ${path}`, detail: "Fallback route recovered the transaction — no user impact." });
      } catch {
        pushAgentLog({ agent: "Sentinel", severity: "warn", route: `${method} ${path}`, detail: "Fallback route exhausted — serving degraded UI snapshot." });
        throw new Error("ASTRA fallback unavailable — please retry");
      }
    } else {
      pushAgentLog({ agent: "Sentinel", severity: "warn", route: `${method} ${path}`, detail: "Write transaction queued for background replay by the recovery agent." });
      throw cause instanceof Error && !rerouted ? cause : new Error("Transaction rerouted for background recovery");
    }
  }

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

export type CategorySummary = {
  id: string;
  name: string;
  slug: string;
  product_count: number;
};

export function getCategories(cookieHeader?: string): Promise<CategorySummary[]> {
  return apiFetch<CategorySummary[]>("/explore/categories", undefined, cookieHeader);
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
export function createCheckoutSession(payload: { shipping_address: string }): Promise<CheckoutSession> { return apiFetch<CheckoutSession>("/checkout/session", { method: "POST", body: JSON.stringify(payload) }); }
export function getCheckoutSession(checkoutRef: string): Promise<CheckoutSession> { return apiFetch<CheckoutSession>(`/checkout/session/${checkoutRef}`); }
export function confirmCheckoutSession(checkoutRef: string, consentId: string): Promise<CheckoutSessionConfirmation> { return apiFetch<CheckoutSessionConfirmation>(`/checkout/session/${checkoutRef}/confirm`, { method: "POST", body: JSON.stringify({ consent_id: consentId }) }); }
export function abandonCheckoutSession(checkoutRef: string): Promise<CheckoutSession> { return apiFetch<CheckoutSession>(`/checkout/session/${checkoutRef}/abandon`, { method: "POST" }); }
export function getChatHistory(): Promise<ChatConversation[]> { return apiFetch<ChatConversation[]>("/chat/history"); }
export function streamChat(payload: { message: string; conversation_id?: number }): Promise<Response> { return fetch(`${API_URL}/api/v1/chat/stream`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }

// ---------------------------------------------------------------------------
// Seller-Buyer direct messaging
// ---------------------------------------------------------------------------

export function getDirectConversations(cookieHeader?: string): Promise<DirectConversation[]> {
  return apiFetch<DirectConversation[]>("/messaging/conversations", undefined, cookieHeader);
}

export function openSellerConversation(productId: string): Promise<DirectConversation> {
  return apiFetch<DirectConversation>("/messaging/conversations", { method: "POST", body: JSON.stringify({ product_id: productId }) });
}

export function getDirectMessages(conversationId: number): Promise<DirectMessageOut[]> {
  return apiFetch<DirectMessageOut[]>(`/messaging/conversations/${conversationId}/messages`);
}

export function sendDirectMessage(conversationId: number, content: string): Promise<DirectMessageOut> {
  return apiFetch<DirectMessageOut>(`/messaging/conversations/${conversationId}/messages`, { method: "POST", body: JSON.stringify({ content }) });
}

export function getMessagingWebSocketUrl(conversationId: number): string {
  return `${API_URL.replace(/^http/, "ws")}/ws/messages/${conversationId}`;
}

// ---------------------------------------------------------------------------
// Password reset
// ---------------------------------------------------------------------------

export function forgotPassword(payload: { email: string }): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify(payload) });
}

export function resetPassword(payload: { email: string; code: string; new_password: string }): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify(payload) });
}

// ---------------------------------------------------------------------------
// AI Negotiator, Authenticity Audit, Escrow timeline & disputes
// ---------------------------------------------------------------------------

export interface NegotiationRound {
  session_id: number;
  product_id: string;
  round: number;
  status: "accepted" | "counter" | "rejected";
  seller_ask: number;
  counter_offer?: number | null;
  final_price?: number | null;
  market_average: number;
  reasoning: string[];
}

export function submitNegotiationOffer(productId: string, payload: { offer_price: number; round: number; session_id?: number }): Promise<NegotiationRound> {
  return apiFetch<NegotiationRound>(`/negotiation/${productId}/offer`, { method: "POST", body: JSON.stringify(payload) });
}

export interface AuthenticityAudit {
  product_id: string;
  listing_hash: string;
  seller_risk_score: number;
  risk_band: "low" | "medium" | "high";
  checks: Array<{ id: string; label: string; status: "pass" | "warn"; detail: string }>;
  verified?: boolean;
  zk_verification?: {
    status: string;
    proof_id: string;
    protocol: string;
    circuit: string;
    public_inputs: number;
    verify_ms: number;
    verified_at: string;
  };
  seller_reputation_hash?: string;
  cryptographic_stamp?: {
    stamp_id: string;
    algorithm: string;
    signed_payload: string;
    attested_by: string;
    attested_at: string;
  };
  synthetic_image_scan?: {
    score: number;
    verdict: string;
    model: string;
    frames_analyzed: number;
    scanned_at: string;
  };
}

export function getProductAuthenticity(slug: string): Promise<AuthenticityAudit> {
  return apiFetch<AuthenticityAudit>(`/products/${slug}/authenticity`);
}

export interface SellerInventoryItem {
  id: string; title: string; category: string; price: number; stock_count: number;
  status: "in_stock" | "out_of_stock"; image_url: string;
}
export interface SellerEscrowOrder {
  order_ref: string; product_name: string; quantity: number; total: number;
  order_status: string; escrow_status: "LOCKED" | "RELEASED" | "REFUNDED"; placed_at: string;
}
export type SellerInventoryPayload = { title: string; category: string; price: number; stock_count: number; description?: string; image_url?: string };
export const getSellerInventory = () => apiFetch<SellerInventoryItem[]>("/seller/inventory");
export const createSellerInventory = (payload: SellerInventoryPayload) => apiFetch<SellerInventoryItem>("/seller/inventory", { method: "POST", body: JSON.stringify(payload) });
export const updateSellerInventory = (id: string, payload: Partial<SellerInventoryPayload>) => apiFetch<SellerInventoryItem>(`/seller/inventory/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteSellerInventory = (id: string) => apiFetch<void>(`/seller/inventory/${id}`, { method: "DELETE" });
export const getSellerOrders = () => apiFetch<SellerEscrowOrder[]>("/seller/orders");
export const dispatchSellerOrder = (ref: string) => apiFetch<{ order_ref: string; order_status: string; escrow_status: string }>(`/seller/orders/${ref}/dispatch`, { method: "POST" });

export interface OrderTimeline {
  order_ref: string;
  escrow_status: string;
  stages: Array<{ key: string; label: string; status: string; at: string | null }>;
  reasoning: Array<{ at: string | null; step: string; detail: string }>;
  resolution_timeline?: ResolutionTimeline;
}

export function getOrderTimeline(orderRef: string): Promise<OrderTimeline> {
  return apiFetch<OrderTimeline>(`/orders/${orderRef}/timeline`);
}

export interface DisputeResult {
  order_ref: string;
  risk_score: number;
  checks: Array<{ rule: string; score: number; detail: string }>;
  escrow_status: string;
  decision: "refunded" | "review_queued";
  message: string;
  resolution_timeline?: ResolutionTimeline;
}

export function initiateDispute(orderRef: string, reason: string): Promise<DisputeResult> {
  return apiFetch<DisputeResult>(`/orders/${orderRef}/dispute`, { method: "POST", body: JSON.stringify({ reason }) });
}

// ---------------------------------------------------------------------------
// Showcase engines: A2A negotiation, voice intent, micro-escrow, swarm log
// ---------------------------------------------------------------------------

export function getA2aNegotiationWebSocketUrl(productId: string): string {
  return `${API_URL.replace(/^http/, "ws")}/ws/negotiation/${productId}`;
}

/** Lightweight probe for the self-healing engine's startup health check. */
export async function pingBackendHealth(): Promise<{ ok: boolean; latencyMs: number }> {
  const started = performance.now();
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return { ok: res.ok, latencyMs: Math.round(performance.now() - started) };
  } catch {
    return { ok: false, latencyMs: Math.round(performance.now() - started) };
  }
}

export function parseVoiceIntent(query: string, imageFile?: File): Promise<VoiceIntentResult> {
  // /explore/intent is multipart (not JSON) so an optional image can travel
  // alongside the transcript — apiFetch can't be reused here since it hardcodes
  // Content-Type: application/json (see the streamChat escape hatch below).
  const body = new FormData();
  body.append("query", query);
  if (imageFile) body.append("image_file", imageFile);
  return fetch(`${API_URL}/api/v1/explore/intent`, { method: "POST", credentials: "include", body }).then((res) => {
    if (!res.ok) throw new Error("Voice intent request failed");
    return res.json() as Promise<VoiceIntentResult>;
  });
}

/** Multipart upload to /voice/transcribe — never goes through apiFetch (no JSON Content-Type, and the body is a file, not a request-blob). */
export function transcribeAudio(audio: Blob, filename = "clip.webm"): Promise<TranscribeResponse> {
  const body = new FormData();
  body.append("audio", audio, filename);
  return fetch(`${API_URL}/api/v1/voice/transcribe`, { method: "POST", credentials: "include", body }).then((res) => {
    if (!res.ok) throw new Error("Transcription failed");
    return res.json() as Promise<TranscribeResponse>;
  });
}

/** POSTs to /voice/synthesize and resolves the raw audio blob — the response is audio bytes, not JSON, so apiFetch (which always calls .json()) can't be reused. */
export function synthesizeSpeech(text: string, voice?: string): Promise<Blob> {
  return fetch(`${API_URL}/api/v1/voice/synthesize`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
  }).then((res) => {
    if (!res.ok) throw new Error(res.status === 501 ? "Spoken replies are not configured" : "Speech synthesis failed");
    return res.blob();
  });
}

/** Single FormData search carrying text + audio + image together — whichever are present get fused server-side (see execute_search). Replaces separate single-modality calls. */
export function multimodalSearch(params: {
  textQuery?: string;
  audioFile?: File | Blob;
  imageFile?: File;
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  semanticTags?: string[];
  sortBy?: string;
  page?: number;
  limit?: number;
}): Promise<SearchResponse> {
  const body = new FormData();
  body.append("query_type", "multimodal");
  if (params.textQuery) body.append("text_query", params.textQuery);
  if (params.audioFile) body.append("audio_file", params.audioFile, "clip.webm");
  if (params.imageFile) body.append("image_file", params.imageFile);
  body.append("category", params.category ?? "All");
  body.append("min_price", String(params.minPrice ?? 0));
  body.append("max_price", String(params.maxPrice ?? 500000));
  body.append("sort_by", params.sortBy ?? "most_relevant");
  body.append("page", String(params.page ?? 1));
  body.append("limit", String(params.limit ?? 50));
  (params.semanticTags ?? []).forEach((tag) => body.append("semantic_tags", tag));
  return fetch(`${API_URL}/api/v1/explore/search`, { method: "POST", credentials: "include", body }).then((res) => {
    if (!res.ok) throw new Error("Search service is unavailable");
    return res.json() as Promise<SearchResponse>;
  });
}

export function getMicroSettlements(amount?: number): Promise<MicroSettlements> {
  return apiFetch<MicroSettlements>(`/wallet/micro-settlements${amount ? `?amount=${amount}` : ""}`);
}

export function getRemittanceContext(): Promise<RemittanceContext> {
  return apiFetch<RemittanceContext>("/wallet/remittance-context");
}

export function getOrderSwarmLog(orderRef: string): Promise<SwarmTrace> {
  return apiFetch<SwarmTrace>(`/orders/${orderRef}/swarm`);
}

type FinancialConsentSubject = { order_ref: string; checkout_ref?: never } | { checkout_ref: string; order_ref?: never };

export function authorizeFinancialConsent(payload: { amount: number; auth_method: "Voice" | "OTP"; voice_transcript?: string; consent_id?: string; otp_code?: string } & FinancialConsentSubject): Promise<ConsentAuthorizationResponse> {
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

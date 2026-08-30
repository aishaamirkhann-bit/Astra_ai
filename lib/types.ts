// Mirrors the FastAPI Pydantic schemas (app/schemas/*.py). Keep these in
// sync with the backend — if a field is renamed there, rename it here too.

export type Verdict = "Good" | "Warning" | "Bad";
export type OverallVerdict = "GOOD TO BUY" | "REVIEW SUGGESTED" | "NOT RECOMMENDED";
export type Fit = "Fits your budget" | "Stretch (Manageable)" | "Over budget";

export interface HeroSuggestion {
  label: string;
  href: string;
}

export interface Product {
  slug: string;
  name: string;
  price_display: string; // "Rs. 314,999"
  price: number;
  rating: number;
  tag: string | null;
  fit: Fit;
  seller: string;
  trust: number;
  category: string;
  image: string | null;
  description: string | null;
}

export interface ProductDetail extends Product {
  images: string[];
  stock_count: number;
  seller_verified: boolean;
  variants: { colors: string[]; sizes: string[]; storage: string[] };
  total_reviews: number;
  rating_breakdown: Record<string, number>;
  sentiment: { positive: number; neutral: number; negative: number };
  reviews: Array<{ id: string; buyer: string; rating: number; comment: string; verified: boolean }>;
}

export interface CartItem { id: number; product_slug: string; name: string; quantity: number; size: string; color: string; storage: string; unit_price: number; image: string; seller_name: string; seller_verified: boolean; stock_count: number; }
export interface Cart { items: CartItem[]; total_quantity: number; subtotal: number; monthly_budget_limit: number; current_spent: number; exceeds_budget: boolean; shipping_address: string; }
export interface CartCheckout { checkout_ref: string; order_refs: string[]; total: number; status: string; }
export interface ChatCard { slug: string; name: string; price: number; image: string; seller: string; trust: number; stock: number; }
export interface ChatMessage { id: number | string; role: "user" | "assistant"; content: string; card_type: "product" | null; card: ChatCard | null; created_at?: string; }
export interface ChatConversation { id: number; title: string; messages: ChatMessage[]; }

export interface DealOut {
  id: string;
  slug: string;
  name: string;
  price_display: string;
  price: number;
  market_price_display: string;
  market_price: number;
  savings_display: string;
  savings: number;
  discount_percent: number;
  rating: number;
  total_reviews: number;
  tag: "Bestseller" | "New" | "Mega Deal";
  trust: {
    overall: number;
    seller_fulfillment: number;
    authenticity_sentiment: number;
    price_stability: number;
    seller_verified: boolean;
    summary: string;
  };
  seller: string;
  category: "Tech" | "Fashion" | "Audio" | "Accessories";
  image: string;
  stock_remaining: number;
  expires_at: string | null;
}

export interface DealDetail extends DealOut {
  description: string;
  gallery: string[];
  sizes: string[];
  colors: string[];
  price_history: Array<{ observed_at: string; label: string; listing_price: number; market_average: number }>;
  audit_reasoning: Record<string, unknown>;
}

export interface DealListResponse {
  items: DealOut[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DealReservationResponse {
  reservation_id: string;
  deal_id: string;
  status: "reserved";
  quantity: number;
  stock_remaining: number;
  expires_at: string;
  order_ref: string;
  message: string;
}

export interface AddToCartResponse {
  message: string;
  quantity: number;
  cart_total_quantity: number;
}

export interface OrderOut {
  order_ref: string;
  product_name: string;
  price: number;
  quantity: number;
  size: string;
  color: string;
  storage: string;
  status: "pending_approval" | "reversal_window_open" | "confirmed" | "shipped" | "delivered" | "cancelled";
  seconds_left: number;
  placed_at: string;
  image: string;
}

export interface OrderDetail extends OrderOut {
  product_id: string;
  unit_price: number;
  subtotal: number;
  seller_name: string;
  seller_verified: boolean;
  seller_trust_score: number;
  payment_method: "Wallet" | "Wallet / Consent Verified";
  consent_method: "Voice" | "OTP" | null;
  shipped_at: string | null;
  delivered_at: string | null;
}

export type NotificationCategory = "deal_match" | "order_update" | "financial_alert";
export interface AstraNotification { id: string; category: NotificationCategory; title: string; message: string; is_read: boolean; created_at: string; href: string | null; deal_id: string | null; goal_id: number | null; }
export interface NotificationList { items: AstraNotification[]; unread_count: number; }

export interface CheckItem {
  label: string;
  detail: string;
  verdict: Verdict;
}

export interface AstraCheckOut {
  checks: CheckItem[];
  overall_verdict: OverallVerdict;
  product_slug: string | null;
}

export interface AstraCheckDashboardStats {
  total_verified_sellers: number;
  flagged_listings: number;
  average_platform_trust_index: number;
  real_time_scans_active: number;
}

export interface TrustInspection {
  product_id: string;
  product_name: string;
  seller: {
    seller_id: string;
    seller_name: string;
    business_name: string;
    verification_status: string;
    business_identity_verified: boolean;
    fulfillment_rate: number;
    return_rate: number;
    dispute_rate: number;
    trust_index: number;
    is_flagged: boolean;
    last_verified_at: string;
  };
  current_price: number;
  market_average: number;
  trust_score: number;
  risk_level: "safe" | "caution" | "flagged";
  seller_score: number;
  review_sentiment_score: number;
  price_stability_score: number;
  price_history: Array<{ observed_at: string; label: string; market_average: number; current_price: number }>;
  deal_eligible: boolean;
  inspected_at: string;
  audit_id: number;
  external_audit_id: string;
  authenticity_flag: boolean;
  price_anomaly_detected: boolean;
  reasoning_summary: string;
}

export interface TrustActionResponse {
  product_id: string;
  action: "manual_override" | "flagged" | "approved_for_deals";
  trust_score: number;
  deal_active: boolean;
  message: string;
}

export interface AiAssistantSuggestion {
  message: string;
  product: Product;
  fits_budget: boolean;
  verified_seller: boolean;
}

export interface ApprovalStatusOut {
  order_ref: string;
  status: "pending" | "approved" | "cancelled";
  seconds_left: number;
  window_seconds: number;
  prompt_text: string;
  amount: number;
}

export interface ApprovalActionResponse {
  order_ref: string;
  status: "approved" | "cancelled";
  message: string;
}

export type PipelineNodeStatus = "done" | "active" | "queued";

export interface PipelineNode {
  key: string;
  label: string;
  status: PipelineNodeStatus;
  latency_display: string;
  log: string;
}

export interface PipelineStateOut {
  order_ref: string | null;
  nodes: PipelineNode[];
  active_index: number;
  current_verdict_label: string;
  is_live: boolean;
}

export type CadencePeriod = "weekly" | "monthly";

export interface GoalOut {
  id: number;
  name: string;
  target_amount: number;
  allocated_amount: number;
  remaining_amount: number;
  percent_funded: number;
  deadline: string | null;
  cadence_amount: number | null;
  cadence_period: CadencePeriod | null;
}

export interface GoalCreatePayload {
  name: string;
  target_amount: number;
  deadline?: string | null;
  cadence_amount?: number | null;
  cadence_period?: CadencePeriod | null;
}

export interface BudgetOverview {
  monthly_limit: number;
  current_spent: number;
  rollover_savings: number;
  available_safe_balance: number;
  spending_percent: number;
  active_goals: number;
  total_goal_savings: number;
  total_ai_deal_savings: number;
}

export interface ShoppingGoalOut {
  goal_id: number;
  target_title: string;
  target_price: number;
  saved_amount: number;
  remaining_amount: number;
  percent_funded: number;
  category: string;
  priority_level: "Low" | "Medium" | "High";
  status: "Active" | "Completed" | "Paused";
  deadline: string | null;
  image_url: string | null;
}

export interface BudgetAlertOut {
  alert_id: string;
  goal_id: number | null;
  deal_id: string | null;
  alert_type: "Deal_Matched" | "Budget_Warning";
  message: string;
  created_at: string;
}

export interface BudgetDashboardOut {
  budget: BudgetOverview;
  goals: ShoppingGoalOut[];
  alerts: BudgetAlertOut[];
}

export interface MatchedDealOut {
  deal_id: string;
  goal_id: number;
  product_id: string;
  product_name: string;
  image: string;
  category: string;
  listing_price: number;
  target_price: number;
  saved_amount: number;
  savings_vs_target: number;
  trust_score: number;
  within_monthly_budget: boolean;
  can_buy_with_allocated_savings: boolean;
  suggested_installment: number | null;
  alert_type: "Deal_Matched" | "Budget_Warning";
  message: string;
}

export interface WalletOut {
  available_balance: number;
  available_balance_display: string;
}

export interface WalletLedgerEntryOut {
  id: string;
  label: string;
  amount: number;
  entry_type: "credit" | "debit";
  transaction_type: "Credit" | "Debit" | "Refund";
  created_at: string;
}

export interface WalletDetailOut extends WalletOut {
  user_id: number;
  ledger: WalletLedgerEntryOut[];
}

export interface ConsentAuthorizationResponse {
  consent_id: string;
  status: "challenge_sent" | "approved";
  auth_method: "Voice" | "OTP";
  expires_in_seconds: number | null;
  message: string;
  dev_otp?: string | null;
}

export interface GoalsWalletRailOut {
  primary_goal: GoalOut | null;
  wallet: WalletOut;
}

export interface HomePageOut {
  hero_suggestions: HeroSuggestion[];
  recommended_products: Product[];
  astra_check: AstraCheckOut | null;
  ai_assistant: AiAssistantSuggestion | null;
  approval: ApprovalStatusOut | null;
  pipeline: PipelineStateOut;
  goals_wallet: GoalsWalletRailOut;
  unread_notifications: number;
  user: LoginResponse["user"];
}

export type UserRole = "buyer" | "seller";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    name: string;
    email: string;
    preferred_language: string;
    role: UserRole;
  };
}

/** Returned by /auth/register and /auth/login instead of a token — 2FA gate. */
export interface OtpRequiredResponse {
  otp_required: true;
  otp_token: string;
  email: string;
  expires_in_minutes: number;
  message: string;
}

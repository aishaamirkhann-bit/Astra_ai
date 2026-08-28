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

export interface WalletOut {
  available_balance: number;
  available_balance_display: string;
}

export interface WalletLedgerEntryOut {
  id: number;
  label: string;
  amount: number;
  entry_type: "credit" | "debit";
  created_at: string;
}

export interface WalletDetailOut extends WalletOut {
  ledger: WalletLedgerEntryOut[];
}

export interface GoalsWalletRailOut {
  primary_goal: GoalOut | null;
  wallet: WalletOut;
}

export interface HomePageOut {
  hero_suggestions: HeroSuggestion[];
  recommended_products: Product[];
  astra_check: AstraCheckOut;
  ai_assistant: AiAssistantSuggestion;
  approval: ApprovalStatusOut | null;
  pipeline: PipelineStateOut;
  goals_wallet: GoalsWalletRailOut;
  unread_notifications: number;
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

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

Verdict = Literal["Good", "Warning", "Bad"]


class CheckItem(BaseModel):
    label: str          # "Financial Fit" | "Seller Trust" | "Price Fairness"
    detail: str          # short human-readable reason
    verdict: Verdict


class AstraCheckOut(BaseModel):
    checks: list[CheckItem]
    overall_verdict: Literal["GOOD TO BUY", "REVIEW SUGGESTED", "NOT RECOMMENDED"]
    product_slug: Optional[str] = None


class DashboardStatsOut(BaseModel):
    total_verified_sellers: int
    flagged_listings: int
    average_platform_trust_index: float
    real_time_scans_active: int


class InspectRequest(BaseModel):
    query: str = Field(min_length=1, max_length=160)


class PricePointOut(BaseModel):
    observed_at: str
    label: str
    market_average: float
    current_price: float


class SellerVerificationOut(BaseModel):
    seller_id: str
    seller_name: str
    business_name: str
    verification_status: str
    business_identity_verified: bool
    fulfillment_rate: float
    return_rate: float
    dispute_rate: float
    trust_index: float
    is_flagged: bool
    last_verified_at: str


class TrustInspectionOut(BaseModel):
    product_id: str
    product_name: str
    seller: SellerVerificationOut
    current_price: float
    market_average: float
    trust_score: float
    risk_level: Literal["safe", "caution", "flagged"]
    seller_score: float
    review_sentiment_score: float
    price_stability_score: float
    price_history: list[PricePointOut]
    deal_eligible: bool
    inspected_at: str
    audit_id: int
    external_audit_id: str
    authenticity_flag: bool
    price_anomaly_detected: bool
    reasoning_summary: str


class SellerProfileOut(BaseModel):
    verification: SellerVerificationOut
    products_count: int
    audit_history: list[dict[str, Any]]


class TrustActionRequest(BaseModel):
    product_id: str
    reason: str = Field(min_length=3, max_length=500)
    score: float | None = Field(default=None, ge=0, le=100)


class TrustActionResponse(BaseModel):
    product_id: str
    action: Literal["manual_override", "flagged", "approved_for_deals"]
    trust_score: float
    deal_active: bool
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)

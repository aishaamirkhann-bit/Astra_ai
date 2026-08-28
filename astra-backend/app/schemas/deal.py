from typing import Literal

from pydantic import BaseModel, Field

DealCategory = Literal["Tech", "Fashion", "Audio", "Accessories"]
DealBadge = Literal["Bestseller", "New", "Mega Deal"]


class TrustScoreBreakdown(BaseModel):
    overall: float = Field(ge=0, le=100)
    seller_fulfillment: float = Field(ge=0, le=100)
    authenticity_sentiment: float = Field(ge=0, le=100)
    price_stability: float = Field(ge=0, le=100)
    seller_verified: bool
    summary: str


class PriceHistoryPoint(BaseModel):
    observed_at: str
    label: str
    listing_price: float
    market_average: float


class DealSummary(BaseModel):
    id: str
    slug: str
    name: str
    price_display: str
    price: float
    market_price_display: str
    market_price: float
    savings_display: str
    savings: float
    discount_percent: float
    rating: float
    total_reviews: int
    tag: DealBadge
    trust: TrustScoreBreakdown
    seller: str
    category: DealCategory
    image: str
    stock_remaining: int
    expires_at: str | None


class DealDetail(DealSummary):
    description: str
    gallery: list[str]
    sizes: list[str]
    colors: list[str]
    price_history: list[PriceHistoryPoint]
    audit_reasoning: dict


class DealListResponse(BaseModel):
    items: list[DealSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReserveDealRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=10)
    size: str | None = None
    color: str | None = None


class DealReservationResponse(BaseModel):
    reservation_id: str
    deal_id: str
    status: Literal["reserved"]
    quantity: int
    stock_remaining: int
    expires_at: str
    message: str

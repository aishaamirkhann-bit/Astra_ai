from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductResearchInput(BaseModel):
    id: str
    slug: str
    name: str
    brand: str | None = None
    category: str
    seller_name: str | None = None


class ResearchSource(BaseModel):
    title: str
    url: str

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Source URLs must use HTTP or HTTPS")
        return value


class ResearchReviewSummary(BaseModel):
    overall_sentiment: str | None = None
    common_complaints: list[str] = Field(default_factory=list)


class ResearchPriceComparison(BaseModel):
    store: str
    price: float | None = None
    currency: str | None = None
    url: str
    fetched_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        return ResearchSource.require_http_url(value)


class ResearchAlternative(BaseModel):
    name: str
    why: str | None = None
    approx_price: str | None = None


class ResearchSellerReport(BaseModel):
    name: str | None = None
    rating: float | None = None
    reputation_signals: list[str] = Field(default_factory=list)
    complaints_or_scam_reports: list[str] = Field(default_factory=list)
    return_policy: str | None = None
    verdict: Literal["trustworthy", "caution", "unknown"] = "unknown"


class ProductResearchOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str | None = None
    specifications: dict[str, str] = Field(default_factory=dict)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    review_summary: ResearchReviewSummary = Field(default_factory=ResearchReviewSummary)
    price_comparison: list[ResearchPriceComparison] = Field(default_factory=list)
    alternatives: list[ResearchAlternative] = Field(default_factory=list)
    warranty_support: str | None = None
    red_flags: list[str] = Field(default_factory=list)
    buying_advice: str | None = None
    seller_report: ResearchSellerReport = Field(default_factory=ResearchSellerReport)
    sources: list[ResearchSource] = Field(default_factory=list)
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    confidence: Literal["low", "medium", "high"] = "low"
    generated_at: datetime
    status: Literal["complete", "partial"]
    message: str | None = None

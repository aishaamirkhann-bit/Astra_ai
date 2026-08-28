from typing import Literal, Optional
from pydantic import BaseModel

Verdict = Literal["Good", "Warning", "Bad"]


class CheckItem(BaseModel):
    label: str          # "Financial Fit" | "Seller Trust" | "Price Fairness"
    detail: str          # short human-readable reason
    verdict: Verdict


class AstraCheckOut(BaseModel):
    checks: list[CheckItem]
    overall_verdict: Literal["GOOD TO BUY", "REVIEW SUGGESTED", "NOT RECOMMENDED"]
    product_slug: Optional[str] = None

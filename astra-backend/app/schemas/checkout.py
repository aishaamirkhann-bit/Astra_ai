from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CheckoutSessionStatus = Literal[
    "awaiting_consent",
    "reversal_window_open",
    "confirmed",
    "cancelled",
    "expired",
]


class CheckoutSessionCreateRequest(BaseModel):
    shipping_address: str = Field(min_length=8, max_length=500)


class CheckoutSessionConfirmRequest(BaseModel):
    consent_id: str | None = None


class CheckoutSessionOut(BaseModel):
    checkout_ref: str
    total: float
    shipping_address: str
    status: CheckoutSessionStatus
    expires_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    order_refs: list[str]


class CheckoutSessionConfirmationOut(CheckoutSessionOut):
    wallet_balance: float
    created: bool

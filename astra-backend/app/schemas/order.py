from typing import Literal

from datetime import datetime
from pydantic import BaseModel


class OrderOut(BaseModel):
    order_ref: str
    product_name: str
    price: float
    quantity: int
    size: str
    color: str
    storage: str = ""
    status: Literal["pending_approval", "reversal_window_open", "confirmed", "shipped", "delivered", "cancelled"]
    seconds_left: int
    placed_at: datetime
    image: str


class OrderDetailOut(OrderOut):
    product_id: str
    unit_price: float
    subtotal: float
    seller_name: str
    seller_verified: bool
    seller_trust_score: int
    payment_method: Literal["Wallet", "Wallet / Consent Verified"]
    consent_method: Literal["Voice", "OTP"] | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None


class ReorderResponse(BaseModel):
    order_ref: str
    cart_total_quantity: int
    message: str


class ReverseOrderResponse(BaseModel):
    order_ref: str
    status: Literal["cancelled"]
    message: str

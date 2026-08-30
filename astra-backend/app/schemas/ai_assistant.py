from pydantic import BaseModel, Field
from app.schemas.product import ProductOut


class AiAssistantSuggestion(BaseModel):
    message: str                 # "Yeh product aapke liye best match hai:"
    product: ProductOut
    fits_budget: bool
    verified_seller: bool


class AddToCartRequest(BaseModel):
    product_slug: str
    quantity: int = Field(default=1, ge=1, le=10)
    size: str = ""
    color: str = ""
    storage: str = ""


class CartItemOut(BaseModel):
    id: int
    product_slug: str
    name: str
    quantity: int
    size: str
    color: str
    storage: str
    unit_price: float
    image: str
    seller_name: str
    seller_verified: bool
    stock_count: int


class CartResponse(BaseModel):
    items: list[CartItemOut]
    total_quantity: int
    subtotal: float
    monthly_budget_limit: float
    current_spent: float
    exceeds_budget: bool
    shipping_address: str = ""


class AddToCartResponse(BaseModel):
    message: str
    quantity: int
    cart_total_quantity: int


class CartUpdateRequest(BaseModel):
    quantity: int = Field(ge=1, le=10)


class CartCheckoutRequest(BaseModel):
    consent_id: str | None = None
    shipping_address: str = Field(min_length=8, max_length=500)


class CartCheckoutResponse(BaseModel):
    checkout_ref: str
    order_refs: list[str]
    total: float
    status: str

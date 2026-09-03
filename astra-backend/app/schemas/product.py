from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    slug: str
    name: str
    price_display: str        # "Rs. 314,999" — formatted for direct rendering
    price: float               # raw number, for calculations on frontend if needed
    rating: float
    tag: Optional[str] = None
    fit: str                   # "Fits your budget" | "Stretch (Manageable)" | "Over budget"
    seller: str
    trust: int
    category: str
    image: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BuyerReviewOut(BaseModel):
    id: str
    buyer: str
    rating: int
    comment: str
    verified: bool = True


class ProductDetailOut(ProductOut):
    images: list[str]
    stock_count: int
    seller_verified: bool
    variants: dict[str, list[str]]
    total_reviews: int
    rating_breakdown: dict[str, int]
    sentiment: dict[str, float]
    reviews: list[BuyerReviewOut]

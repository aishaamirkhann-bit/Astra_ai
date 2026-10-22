from typing import NotRequired, TypedDict


class ProductModel(TypedDict):
    id: str
    title: str
    category: str
    category_id: str | None
    origin_country: NotRequired[str]
    price: float
    rating: float
    total_reviews: int
    seller_name: str
    is_verified_seller: bool
    badge: str | None
    image_url: str
    semantic_tags: list[str]
    description: str
    fit: str
    trust: int
    search_terms: str


class WalletModel(TypedDict):
    available_balance: float

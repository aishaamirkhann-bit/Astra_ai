from pydantic import BaseModel, ConfigDict, Field


class ProductSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    price: float
    formatted_price: str
    rating: float = Field(ge=0, le=5)
    total_reviews: int = Field(ge=0)
    seller_name: str
    is_verified_seller: bool
    badge: str | None
    image_url: str
    semantic_tags: list[str]
    trust: int = Field(ge=0, le=100)


class ProductDetailSchema(ProductSchema):
    description: str
    fit: str


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_results: int = Field(ge=0)
    current_page: int = Field(ge=1)
    total_pages: int = Field(ge=0)
    query: str | None = None
    items: list[ProductSchema]


class WalletResponse(BaseModel):
    available_balance: float = Field(ge=0)
    formatted_balance: str


class BudgetRecommendationResponse(SearchResponse):
    available_balance: float = Field(ge=0)

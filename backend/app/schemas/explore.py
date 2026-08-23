from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class SortBy(str, Enum):
    MOST_RELEVANT = "most_relevant"
    PRICE_LOW_HIGH = "price_low_high"
    PRICE_HIGH_LOW = "price_high_low"
    RATING = "rating"


class ExploreSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query_type: QueryType = QueryType.TEXT
    text_query: str | None = Field(default=None, max_length=500)
    category: str = Field(default="All", max_length=80)
    min_price: float = Field(default=0, ge=0)
    max_price: float = Field(default=500000, ge=0)
    semantic_tags: list[str] = Field(default_factory=list, max_length=10)
    sort_by: SortBy = SortBy.MOST_RELEVANT
    page: Annotated[int, Field(ge=1)] = 1
    limit: Annotated[int, Field(ge=1, le=50)] = 10

    @model_validator(mode="after")
    def validate_price_range(self) -> "ExploreSearchRequest":
        if self.min_price > self.max_price:
            raise ValueError("min_price cannot be greater than max_price")
        return self


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


class ProductDetailSchema(ProductSchema):
    description: str
    fit: str
    trust: int = Field(ge=0, le=100)


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

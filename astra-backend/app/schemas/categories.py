from pydantic import BaseModel, ConfigDict


class CategorySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    slug: str
    product_count: int


class CategoryProductsResponse(BaseModel):
    total_results: int
    current_page: int
    total_pages: int
    items: list[dict]

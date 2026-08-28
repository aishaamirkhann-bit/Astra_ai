from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.schemas.explore import BudgetRecommendationResponse, ExploreSearchRequest, ProductDetailSchema, ProductSchema, SearchResponse, WalletResponse
from app.services.budget import get_available_balance, recommend_with_budget
from app.services.explore import execute_search, get_product, list_products

router = APIRouter(prefix="/api/v1/explore", tags=["Explore"])


@router.get("/wallet", response_model=WalletResponse)
async def wallet() -> WalletResponse:
    balance = get_available_balance()
    return WalletResponse(available_balance=balance, formatted_balance=f"Rs. {balance:,.0f}")


@router.get("/products", response_model=list[ProductSchema])
async def products() -> list[ProductSchema]:
    return list_products()


@router.get("/products/{product_id}", response_model=ProductDetailSchema)
async def product(product_id: str) -> ProductDetailSchema:
    return get_product(product_id)


@router.post("/budget-recommendations", response_model=BudgetRecommendationResponse)
async def budget_recommendations(
    text_query: Annotated[str | None, Form()] = None,
    category: Annotated[str, Form()] = "All",
    min_price: Annotated[float, Form()] = 0,
    max_price: Annotated[float, Form()] = 500000,
    page: Annotated[int, Form()] = 1,
    limit: Annotated[int, Form()] = 50,
) -> BudgetRecommendationResponse:
    request = ExploreSearchRequest.model_validate({
        "text_query": text_query,
        "category": category,
        "min_price": min_price,
        "max_price": max_price,
        "page": page,
        "limit": limit,
    })
    results = recommend_with_budget(text_query or "", request)
    start = (page - 1) * limit
    items = results[start : start + limit]
    return BudgetRecommendationResponse(
        total_results=len(results),
        current_page=page,
        total_pages=(len(results) + limit - 1) // limit,
        query=text_query,
        available_balance=get_available_balance(),
        items=items,
    )


@router.post("/search", response_model=SearchResponse)
async def search(
    query_type: Annotated[str, Form()] = "text",
    text_query: Annotated[str | None, Form()] = None,
    category: Annotated[str, Form()] = "All",
    min_price: Annotated[float, Form()] = 0,
    max_price: Annotated[float, Form()] = 500000,
    semantic_tags: Annotated[list[str] | None, Form()] = None,
    sort_by: Annotated[str, Form()] = "most_relevant",
    page: Annotated[int, Form()] = 1,
    limit: Annotated[int, Form()] = 10,
    audio_file: UploadFile | None = File(default=None),
    image_file: UploadFile | None = File(default=None),
) -> SearchResponse:
    try:
        request = ExploreSearchRequest.model_validate({
            "query_type": query_type,
            "text_query": text_query,
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "semantic_tags": semantic_tags or [],
            "sort_by": sort_by,
            "page": page,
            "limit": limit,
        })
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    results, resolved_query = await execute_search(request, audio_file, image_file)
    start = (request.page - 1) * request.limit
    items = results[start : start + request.limit]
    total_pages = (len(results) + request.limit - 1) // request.limit
    return SearchResponse(
        total_results=len(results),
        current_page=request.page,
        total_pages=total_pages,
        query=resolved_query,
        items=items,
    )

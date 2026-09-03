from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.schemas.explore import BudgetRecommendationResponse, ExploreSearchRequest, ProductDetailSchema, ProductSchema, SearchResponse, WalletResponse
from app.schemas.categories import CategoryProductsResponse, CategorySchema
from app.repository import product_repository
from app.services.budget import get_available_balance, recommend_with_budget
from app.services.explore import execute_search, extract_image_features, get_product, list_products, resolve_purchase_intent

router = APIRouter(prefix="/explore", tags=["Explore"])


@router.post("/intent")
async def voice_intent(
    query: Annotated[str, Form(min_length=1, max_length=400)],
    image_file: UploadFile | None = File(default=None),
) -> dict:
    """Voice-to-Action: extract budget/category/action and the best matching product.
    Multipart (not JSON) so an optional image can travel alongside the transcript —
    previously an image could never reach intent resolution at all."""
    image_labels = None
    if image_file is not None:
        image_result = await extract_image_features(image_file)
        image_labels = image_result.labels
    return resolve_purchase_intent(query, image_labels)


@router.get("/categories", response_model=list[CategorySchema])
async def categories() -> list[CategorySchema]:
    return product_repository.list_categories()


@router.get("/categories/{category_slug}/products", response_model=CategoryProductsResponse)
async def category_products(
    category_slug: str,
    min_price: float = 0,
    max_price: float = 500000,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "most_relevant",
    verified_only: bool = False,
    min_rating: float = 0,
) -> CategoryProductsResponse:
    if min_price < 0 or max_price < min_price or min_rating < 0 or min_rating > 5 or page < 1 or not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail="Invalid category product filters")
    items, total = product_repository.list_category_products(category_slug, min_price, max_price, page, limit, sort_by, verified_only, min_rating)
    return CategoryProductsResponse(
        total_results=total,
        current_page=page,
        total_pages=(total + limit - 1) // limit,
        items=items,
    )


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
    fused = await execute_search(request, audio_file, image_file)
    start = (request.page - 1) * request.limit
    items = fused.results[start : start + request.limit]
    total_pages = (len(fused.results) + request.limit - 1) // request.limit
    return SearchResponse(
        total_results=len(fused.results),
        current_page=request.page,
        total_pages=total_pages,
        query=fused.query,
        items=items,
        fusion_signals=[
            {
                "source": signal.source, "text": signal.text, "weight": signal.weight,
                "provider": signal.provider, "confidence": signal.confidence,
            }
            for signal in fused.signals if signal.text
        ],
        image_labels=fused.image_labels,
    )

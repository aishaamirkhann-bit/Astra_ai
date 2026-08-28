from typing import Any

from app.schemas.explore import ExploreSearchRequest
from app.services.explore import _keyword_score, _to_response_product
from app.repository import product_repository

AVAILABLE_BALANCE = 25000.0


def get_available_balance() -> float:
    return AVAILABLE_BALANCE


def recommend_with_budget(query: str, request: ExploreSearchRequest) -> list[dict[str, Any]]:
    products = []
    for product in product_repository.list_products():
        if product["price"] > AVAILABLE_BALANCE:
            continue
        if request.category.lower() != "all" and product["category"].lower() != request.category.lower():
            continue
        if not request.min_price <= product["price"] <= request.max_price:
            continue
        relevance = _keyword_score(query, product) if query.strip() else 0.0
        affordability = 1 - (product["price"] / AVAILABLE_BALANCE)
        score = relevance * 0.65 + affordability * 0.25 + (product["rating"] / 5) * 0.10
        products.append((score, product))

    products.sort(key=lambda item: item[0], reverse=True)
    return [_to_response_product(product) for _, product in products]

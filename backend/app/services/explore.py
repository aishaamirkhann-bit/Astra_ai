import re
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, UploadFile, status

from app.repository import product_repository
from app.schemas.explore import ExploreSearchRequest, ProductDetailSchema, QueryType, SortBy


async def process_voice_query(audio_file: UploadFile) -> str:
    """Placeholder for Whisper/STT; the returned text is deterministic for local development."""
    if audio_file.content_type not in {"audio/mpeg", "audio/wav", "audio/ogg", "audio/webm"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio format")
    await audio_file.read()
    return "gaming laptop 200k ke under"


async def extract_image_features(image_file: UploadFile) -> str:
    """Placeholder for a vision encoder; production code should persist no raw upload."""
    if not image_file.content_type or not image_file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported image format")
    await image_file.read()
    return "smartphone mobile"


def parse_query_intent(query: str) -> tuple[str, float | None, list[str]]:
    normalized = query.lower().replace(",", "")
    budget: float | None = None
    amount = re.search(
        r"(?:under|below|less than|ke under|tak|budget)\s*(\d+(?:\.\d+)?)\s*(k|thousand|lac|lakh)?|"
        r"(\d+(?:\.\d+)?)\s*(k|thousand|lac|lakh)?\s*(?:under|below|ke under|tak)",
        normalized,
    )
    if amount:
        number = amount.group(1) or amount.group(3)
        multiplier = amount.group(2) or amount.group(4)
        budget = float(number)
        if multiplier in {"k", "thousand"}:
            budget *= 1000
        elif multiplier in {"lac", "lakh"}:
            budget *= 100000

    tags: list[str] = []
    tag_terms = {
        "bestseller": "Bestseller", "best seller": "Bestseller",
        "deal": "Deal", "new": "New", "verified": "Verified seller",
    }
    for term, tag in tag_terms.items():
        if term in normalized and tag not in tags:
            tags.append(tag)
    return normalized, budget, tags


def _keyword_score(query: str, product: dict[str, Any]) -> float:
    stop_words = {"a", "an", "and", "for", "in", "ke", "ko", "under", "the", "to"}
    tokens = {token for token in re.findall(r"[a-z0-9]+", query) if token not in stop_words}
    searchable_text = " ".join([
        product["title"], product["category"], product["description"],
        product["search_terms"], " ".join(product["semantic_tags"]),
    ]).lower()
    product_tokens = set(re.findall(r"[a-z0-9]+", searchable_text))
    return len(tokens & product_tokens) / max(len(tokens), 1)


def _to_response_product(product: dict[str, Any]) -> dict[str, Any]:
    search_fields = {
        "id", "title", "category", "price", "rating", "total_reviews",
        "seller_name", "is_verified_seller", "badge", "image_url", "semantic_tags",
    }
    return {key: value for key, value in product.items() if key in search_fields} | {
        "formatted_price": f"Rs. {product['price']:,.0f}"
    }


def get_product(product_id: str) -> ProductDetailSchema:
    product = product_repository.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductDetailSchema.model_validate(
        _to_response_product(product) | {
            "description": product["description"],
            "fit": product["fit"],
            "trust": product["trust"],
        }
    )


def list_products() -> list[dict[str, Any]]:
    return [_to_response_product(product) for product in product_repository.list_products()]


def hybrid_vector_search(query: str, request: ExploreSearchRequest) -> list[dict[str, Any]]:
    """Combine lexical overlap with a deterministic semantic proxy, then apply strict filters."""
    normalized, inferred_budget, inferred_tags = parse_query_intent(query)
    max_price = min(request.max_price, inferred_budget) if inferred_budget else request.max_price
    requested_tags = set(request.semantic_tags) | set(inferred_tags)
    category = request.category.lower()

    candidates = []
    for product in product_repository.list_products():
        if category != "all" and product["category"].lower() != category:
            continue
        if not request.min_price <= product["price"] <= max_price:
            continue
        if requested_tags and not requested_tags.issubset(set(product["semantic_tags"])):
            continue
        lexical = _keyword_score(normalized, product)
        tag_match = bool(requested_tags.intersection(product["semantic_tags"]))
        if normalized.strip() and lexical == 0 and not tag_match:
            continue
        candidates.append((lexical * 0.7 + (0.2 if tag_match else 0) + product["rating"] / 100, product))

    if request.sort_by == SortBy.PRICE_LOW_HIGH:
        candidates.sort(key=lambda item: item[1]["price"])
    elif request.sort_by == SortBy.PRICE_HIGH_LOW:
        candidates.sort(key=lambda item: item[1]["price"], reverse=True)
    elif request.sort_by == SortBy.RATING:
        candidates.sort(key=lambda item: item[1]["rating"], reverse=True)
    else:
        candidates.sort(key=lambda item: item[0], reverse=True)
    return [_to_response_product(product) for _, product in candidates]


async def execute_search(request: ExploreSearchRequest, audio_file: UploadFile | None, image_file: UploadFile | None) -> tuple[list[dict[str, Any]], str]:
    if request.query_type == QueryType.VOICE:
        if audio_file is None:
            raise HTTPException(status_code=422, detail="audio_file is required for voice searches")
        query = await process_voice_query(audio_file)
    elif request.query_type == QueryType.IMAGE:
        if image_file is None:
            raise HTTPException(status_code=422, detail="image_file is required for image searches")
        query = await extract_image_features(image_file)
    else:
        query = request.text_query or ""
    return hybrid_vector_search(query, request), query

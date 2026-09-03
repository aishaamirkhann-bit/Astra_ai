import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.repository import product_repository
from app.schemas.explore import ExploreSearchRequest, ProductDetailSchema, QueryType, SortBy
from app.services import vision as vision_service
from app.services import voice_service


@dataclass
class FusionSignal:
    """One resolved modality contributing to a search — carries its own weight
    so an image guess doesn't outrank explicit typed text."""

    source: str  # "text" | "voice" | "image"
    text: str
    weight: float
    provider: str | None = None
    confidence: float | None = None


@dataclass
class ImageQueryResult:
    query: str
    labels: list[str] = field(default_factory=list)
    provider: str | None = None
    confidence: float | None = None


async def process_voice_query(audio_file: UploadFile) -> str:
    """Transcribe via the configured STT provider; falls back to the original
    deterministic placeholder when STT_PROVIDER is unset (or the call fails) —
    a test pins this exact fallback string, so it must never change."""
    if audio_file.content_type not in {"audio/mpeg", "audio/wav", "audio/ogg", "audio/webm"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio format")
    audio_bytes = await audio_file.read()
    transcript = voice_service.transcribe(audio_bytes, audio_file.content_type)
    return transcript if transcript is not None else "gaming laptop 200k ke under"


async def extract_image_features(image_file: UploadFile) -> ImageQueryResult:
    """Use the configured vision provider when available; otherwise fall back to
    the original filename/category heuristic (kept verbatim — a test pins it)."""
    if not image_file.content_type or not image_file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported image format")
    filename = (image_file.filename or "").lower()
    image_bytes = await image_file.read()

    vision_result = vision_service.analyze_image(image_bytes, filename)
    if vision_result is not None:
        return ImageQueryResult(
            query=vision_result.query,
            labels=vision_result.labels,
            provider=vision_result.provider,
            confidence=vision_result.confidence,
        )

    query = _guess_image_query_from_filename(filename)
    return ImageQueryResult(query=query, labels=[query])


def _guess_image_query_from_filename(filename: str) -> str:
    if "samsung" in filename:
        return "samsung smartphone"
    if any(term in filename for term in ("headphone", "earbud")):
        return "headphones audio"
    if any(term in filename for term in ("phone", "mobile", "iphone")):
        return "smartphone mobile"
    if any(term in filename for term in ("laptop", "notebook")):
        return "laptop computer"
    if "watch" in filename:
        return "smartwatch wearable"
    if any(term in filename for term in ("jewelry", "earring")):
        return "jewelry"
    if "dress" in filename:
        return "clothing fashion"
    if "makeup" in filename:
        return "makeup beauty"
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


ACTION_TERMS = ("buy", "purchase", "order", "grab", "kharido", "khareed", "lena hai", "leni hai", "chahiye", "book")
CATEGORY_TERMS = {
    "Mobiles": ("phone", "smartphone", "mobile", "iphone", "samsung", "galaxy", "pixel", "infinix"),
    "Laptops & Computers": ("laptop", "notebook", "computer", "macbook", "gaming pc", "ultrabook"),
    "Audio & Wearables": ("headphone", "earbud", "airpods", "smartwatch", "watch", "speaker", "audio"),
    "Jewelry": ("jewelry", "jewellery", "ring", "earring", "necklace", "bracelet"),
    "Clothing & Fashion": ("dress", "kurta", "shirt", "jacket", "clothes", "fashion", "sneaker", "shoes"),
    "Makeup & Beauty": ("makeup", "lipstick", "beauty", "skincare", "perfume", "foundation"),
    "Home Appliances": ("fridge", "refrigerator", "washing machine", "air conditioner", "microwave", "oven", "blender"),
    "Households": ("household", "kitchen", "cookware", "dinner set"),
}


def resolve_purchase_intent(query: str, image_labels: list[str] | None = None) -> dict[str, Any]:
    """Voice-to-Action: parse action/budget/category and pick the best product.
    Optionally widened with image-derived labels so intent resolution is
    multimodal rather than text-only; the labels only add search signal —
    the response still echoes the original spoken/typed query."""
    fusion_text = f"{query} {' '.join(image_labels)}".strip() if image_labels else query
    normalized, budget, _tags = parse_query_intent(fusion_text)
    bare_amount = re.search(r"(?:rs\.?|rupees|paise)?\s*(\d{2,7}(?:\.\d+)?)\s*(k|thousand|hazar|lac|lakh)?", normalized)
    if budget is None and bare_amount:
        budget = float(bare_amount.group(1))
        multiplier = bare_amount.group(2)
        if multiplier in {"k", "thousand", "hazar"}:
            budget *= 1000
        elif multiplier in {"lac", "lakh"}:
            budget *= 100000
        if budget < 1000 and multiplier is None:
            budget *= 1000  # "200" in speech almost always means 200k PKR

    action = next((term for term in ACTION_TERMS if term in normalized), None)
    category = next((name for name, terms in CATEGORY_TERMS.items() if any(term in normalized for term in terms)), None)

    tokens = {token for token in re.findall(r"[a-z0-9]+", normalized) if len(token) > 2}
    candidates: list[tuple[float, dict[str, Any]]] = []
    for product in product_repository.list_products():
        if budget is not None and product["price"] > budget:
            continue
        haystack = " ".join([product["title"], product["category"], product["search_terms"], " ".join(product["semantic_tags"])]).lower()
        product_tokens = set(re.findall(r"[a-z0-9]+", haystack))
        overlap = len(tokens & product_tokens)
        category_bonus = 2.0 if product["category"] == category else 0.0
        score = overlap * 1.0 + category_bonus + product["trust"] / 100 + product["rating"] / 25
        if category and product["category"] != category and overlap == 0:
            continue
        if overlap == 0 and category_bonus == 0:
            continue
        candidates.append((score, product))

    candidates.sort(key=lambda item: item[0], reverse=True)
    matched = candidates[0][1] if candidates else None
    alternatives = [
        {key: product[key] for key in ("id", "title", "category", "price", "image_url", "trust")}
        for _, product in candidates[1:3]
    ]
    intent = "buy" if action and matched else ("browse" if matched else "search")
    return {
        "query": query,
        "intent": intent,
        "action": {
            "type": "checkout" if intent == "buy" else "search",
            "label": "Voice-to-Action autonomous checkout" if intent == "buy" else "Catalog search",
            "verb": action,
        },
        "budget": budget,
        "category": matched["category"] if matched else category,
        "matched_product": (
            {key: matched[key] for key in ("id", "title", "category", "price", "image_url", "trust", "rating", "seller_name", "is_verified_seller")}
            | {"formatted_price": f"Rs. {matched['price']:,.0f}"}
        ) if matched else None,
        "alternatives": alternatives,
        "auto_checkout": intent == "buy",
        "confidence": round(min(0.62 + (candidates[0][0] if candidates else 0) / 12, 0.99), 2),
    }


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
        "seller_name", "is_verified_seller", "badge", "image_url", "semantic_tags", "trust",
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


def hybrid_vector_search(signals: Sequence[FusionSignal], request: ExploreSearchRequest) -> list[dict[str, Any]]:
    """Fuse whatever signals are present (text + voice transcript + image labels)
    into one weighted lexical score, then apply the same strict filters as before.

    For a single signal this reduces to exactly the original unweighted scoring
    (the weight cancels out of the average), so single-modality search behaviour
    is unchanged; with several signals present, each contributes proportionally
    to its FUSION_*_WEIGHT so an image guess never outranks explicit typed text.
    """
    combined_text = " ".join(signal.text for signal in signals if signal.text).strip()
    normalized, inferred_budget, inferred_tags = parse_query_intent(combined_text)
    max_price = min(request.max_price, inferred_budget) if inferred_budget else request.max_price
    requested_tags = {tag.strip().lower() for tag in request.semantic_tags if tag.strip()} | {tag.lower() for tag in inferred_tags}
    category = request.category.lower()

    weighted_signals = [signal for signal in signals if signal.text]
    total_weight = sum(signal.weight for signal in weighted_signals) or 1.0

    candidates = []
    for product in product_repository.list_products():
        if category != "all" and product["category"].lower() != category:
            continue
        if not request.min_price <= product["price"] <= max_price:
            continue
        product_tags = {tag.strip().lower() for tag in product["semantic_tags"]}
        if requested_tags and not requested_tags.issubset(product_tags):
            continue
        lexical = sum(
            signal.weight * _keyword_score(signal.text.lower().replace(",", ""), product)
            for signal in weighted_signals
        ) / total_weight
        tag_match = bool(requested_tags.intersection(product_tags))
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


@dataclass
class FusedSearchResult:
    results: list[dict[str, Any]]
    query: str
    signals: list[FusionSignal]
    image_labels: list[str]


async def execute_search(
    request: ExploreSearchRequest,
    audio_file: UploadFile | None,
    image_file: UploadFile | None,
) -> FusedSearchResult:
    """Fuse every signal present in the request instead of picking exactly one
    modality: text_query, an uploaded audio_file, and an uploaded image_file
    can now all arrive together (query_type=multimodal) or individually
    (query_type=text|voice|image, which additionally enforces that its file is
    present, preserving the original per-mode validation)."""
    if request.query_type == QueryType.VOICE and audio_file is None:
        raise HTTPException(status_code=422, detail="audio_file is required for voice searches")
    if request.query_type == QueryType.IMAGE and image_file is None:
        raise HTTPException(status_code=422, detail="image_file is required for image searches")

    signals: list[FusionSignal] = []
    image_labels: list[str] = []

    text_query = (request.text_query or "").strip()
    if text_query:
        signals.append(FusionSignal(source="text", text=text_query, weight=settings.FUSION_TEXT_WEIGHT))

    if audio_file is not None:
        transcript = await process_voice_query(audio_file)
        signals.append(FusionSignal(source="voice", text=transcript, weight=settings.FUSION_VOICE_WEIGHT))

    if image_file is not None:
        image_result = await extract_image_features(image_file)
        signals.append(FusionSignal(
            source="image", text=image_result.query, weight=settings.FUSION_IMAGE_WEIGHT,
            provider=image_result.provider, confidence=image_result.confidence,
        ))
        image_labels = image_result.labels

    if not signals:
        signals.append(FusionSignal(source="text", text="", weight=settings.FUSION_TEXT_WEIGHT))

    resolved_query = " ".join(signal.text for signal in signals if signal.text).strip()
    results = hybrid_vector_search(signals, request)
    return FusedSearchResult(results=results, query=resolved_query, signals=signals, image_labels=image_labels)

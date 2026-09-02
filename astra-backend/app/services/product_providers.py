import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import settings


log = logging.getLogger("astra.product_providers")


class ProviderUnavailable(RuntimeError):
    pass


_token_lock = threading.Lock()
_ebay_token: dict[str, Any] = {"value": None, "expires_at": 0.0}
_hardcoded_products: list[dict[str, Any]] | None = None
_image_resolver: Callable[[str], str] | None = None

_CATEGORY_KEYWORDS = (
    ("Mobiles", ("mobile", "phone", "smartphone", "tablet", "iphone", "android")),
    ("Laptops & Computers", ("laptop", "computer", "notebook", "desktop", "monitor", "pc")),
    ("Audio & Wearables", ("audio", "headphone", "earbud", "speaker", "watch", "wearable")),
    ("Jewelry", ("jewelry", "jewellery", "ring", "earring", "necklace", "bracelet")),
    ("Clothing & Fashion", ("clothing", "fashion", "dress", "shirt", "shoe", "sneaker", "apparel")),
    ("Makeup & Beauty", ("makeup", "beauty", "lipstick", "skincare", "cosmetic", "perfume")),
    ("Home Appliances", ("appliance", "air fryer", "refrigerator", "washing machine", "microwave")),
)


def configure_catalog_defaults(products: list[dict[str, Any]], image_resolver: Callable[[str], str]) -> None:
    global _hardcoded_products, _image_resolver
    _hardcoded_products = products
    _image_resolver = image_resolver


def _catalog_defaults() -> tuple[list[dict[str, Any]], Callable[[str], str] | None]:
    if _hardcoded_products is None:
        from app.data import HARDCODED_PRODUCTS, _image

        configure_catalog_defaults(HARDCODED_PRODUCTS, _image)
    return _hardcoded_products or [], _image_resolver


def _timeout() -> float:
    return settings.PRODUCT_PROVIDER_TIMEOUT_SECONDS


def _slugify(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    return slug


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, dict):
        value = value.get("value") or value.get("price") or value.get("amount")
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else default


def _integer(value: Any, default: int = 0) -> int:
    number = _number(value)
    return max(0, int(number)) if number is not None else default


def _boolean(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _category(value: Any) -> str:
    text = str(value or "").casefold()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "Households"


def _image_key(category: str) -> str:
    return {
        "Mobiles": "smartphone,samsung",
        "Laptops & Computers": "laptop,lenovo",
        "Audio & Wearables": "headphones,wireless",
        "Jewelry": "earrings,goldjewelry",
        "Clothing & Fashion": "embroidery,fabric",
        "Makeup & Beauty": "lipstick,cosmetics",
        "Home Appliances": "kitchenappliance",
    }.get(category, "")


def _image_url(value: Any, category: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    _, resolver = _catalog_defaults()
    return resolver(_image_key(category)) if resolver else "/images/products/fallback-tech.jpg"


def _badge(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"bestseller", "best seller", "top rated"}:
        return "Bestseller"
    if normalized in {"new", "new arrival"}:
        return "New"
    if normalized in {"deal", "sale", "discount"}:
        return "Deal"
    return None


def _tags(badge: str | None, verified: bool, rating: float) -> list[str]:
    tags: list[str] = []
    if verified:
        tags.append("Verified seller")
    if badge:
        tags.append(badge)
    if rating >= 4.7:
        tags.append("Highly rated")
    return tags or ["Verified seller"]


def _search_terms(title: str, category: str, brand: Any = "") -> str:
    tokens = re.findall(r"[a-z0-9]+", f"{title} {category} {brand}".casefold())
    return " ".join(dict.fromkeys(tokens))


def _product(
    *,
    title: Any,
    category: Any,
    price: Any,
    rating: Any = None,
    total_reviews: Any = None,
    seller_name: Any = None,
    is_verified_seller: Any = True,
    badge: Any = None,
    image_url: Any = None,
    description: Any = None,
    trust: Any = None,
    brand: Any = None,
) -> dict[str, Any]:
    normalized_title = str(title or "").strip()
    normalized_price = _number(price)
    if not normalized_title or normalized_price is None or normalized_price <= 0:
        raise ProviderUnavailable("provider item is missing a title or positive price")

    normalized_category = _category(category or normalized_title)
    normalized_rating = min(5.0, max(0.0, _number(rating, 4.5) or 4.5))
    normalized_verified = _boolean(is_verified_seller)
    normalized_badge = _badge(badge)
    normalized_description = str(description or normalized_title).strip() or normalized_title
    normalized_trust = _integer(trust, 90) if trust is not None else 90

    return {
        "id": _slugify(normalized_title),
        "title": normalized_title,
        "category": normalized_category,
        "price": float(normalized_price),
        "rating": normalized_rating,
        "total_reviews": _integer(total_reviews),
        "seller_name": str(seller_name or brand or "Marketplace seller").strip() or "Marketplace seller",
        "is_verified_seller": normalized_verified,
        "badge": normalized_badge,
        "image_url": _image_url(image_url, normalized_category),
        "semantic_tags": _tags(normalized_badge, normalized_verified, normalized_rating),
        "description": normalized_description,
        "fit": "Fits your budget",
        "trust": min(100, max(0, normalized_trust)),
        "search_terms": _search_terms(normalized_title, normalized_category, brand),
    }


def _deduplicate(products: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for product in products:
        base_id = product["id"]
        seen[base_id] = seen.get(base_id, 0) + 1
        if seen[base_id] > 1:
            product["id"] = f"{base_id}-{seen[base_id]}"
        result.append(product)
        if len(result) == limit:
            break
    return result


def _ebay_access_token() -> str:
    if not settings.EBAY_CLIENT_ID or not settings.EBAY_CLIENT_SECRET:
        raise ProviderUnavailable("eBay credentials are not configured")

    now = time.monotonic()
    with _token_lock:
        if _ebay_token["value"] and now < _ebay_token["expires_at"]:
            return str(_ebay_token["value"])

    try:
        response = httpx.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            auth=httpx.BasicAuth(settings.EBAY_CLIENT_ID, settings.EBAY_CLIENT_SECRET),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        expires_in = _integer(payload.get("expires_in"), 0)
    except Exception as cause:
        raise ProviderUnavailable(f"eBay token request failed: {cause}") from cause

    if not token or expires_in <= 0:
        raise ProviderUnavailable("eBay token response is invalid")

    with _token_lock:
        _ebay_token["value"] = token
        _ebay_token["expires_at"] = time.monotonic() + max(1, expires_in - 60)
    return token


def _ebay_category(item: dict[str, Any]) -> str:
    categories = item.get("categories")
    if isinstance(categories, list) and categories and isinstance(categories[0], dict):
        return str(categories[0].get("categoryName") or "")
    return str(item.get("categoryPath") or "")


def fetch_from_ebay(query: str = "", limit: int = 11) -> list[dict]:
    try:
        response = httpx.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {_ebay_access_token()}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            params={"q": query or "popular products", "limit": limit},
            timeout=_timeout(),
        )
        response.raise_for_status()
        items = response.json().get("itemSummaries")
    except ProviderUnavailable:
        raise
    except Exception as cause:
        raise ProviderUnavailable(f"eBay browse request failed: {cause}") from cause

    if not isinstance(items, list):
        raise ProviderUnavailable("eBay returned no item summaries")

    products: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        seller = item.get("seller") if isinstance(item.get("seller"), dict) else {}
        try:
            products.append(_product(
                title=item.get("title"),
                category=_ebay_category(item),
                price=item.get("price"),
                rating=item.get("rating"),
                total_reviews=item.get("reviewCount") or seller.get("feedbackScore"),
                seller_name=seller.get("username"),
                is_verified_seller=_number(seller.get("feedbackPercentage"), 100) >= 98,
                badge="Bestseller" if item.get("topRatedBuyingExperience") else None,
                image_url=(item.get("image") or {}).get("imageUrl") if isinstance(item.get("image"), dict) else None,
                description=item.get("shortDescription"),
                trust=seller.get("feedbackPercentage"),
            ))
        except ProviderUnavailable:
            continue

    products = _deduplicate(products, limit)
    if not products:
        raise ProviderUnavailable("eBay returned no usable products")
    return products


def _rapidapi_items(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        products = data.get("products") or data.get("items")
        if isinstance(products, list):
            return [item for item in products if isinstance(item, dict)]
    return []


def _rapidapi_image(item: dict[str, Any]) -> Any:
    photos = item.get("product_photos") or item.get("images")
    if isinstance(photos, list) and photos:
        return photos[0]
    return item.get("product_photo") or item.get("thumbnail")


def fetch_from_rapidapi(query: str = "", limit: int = 11) -> list[dict]:
    if not settings.RAPIDAPI_KEY or not settings.RAPIDAPI_HOST:
        raise ProviderUnavailable("RapidAPI credentials are not configured")

    try:
        response = httpx.get(
            f"https://{settings.RAPIDAPI_HOST}/search",
            headers={
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": settings.RAPIDAPI_HOST,
            },
            params={"q": query or "popular products", "country": "us", "language": "en", "limit": limit},
            timeout=_timeout(),
        )
        response.raise_for_status()
        items = _rapidapi_items(response.json())
    except Exception as cause:
        raise ProviderUnavailable(f"RapidAPI search request failed: {cause}") from cause

    products: list[dict[str, Any]] = []
    for item in items:
        try:
            products.append(_product(
                title=item.get("product_title") or item.get("title"),
                category=item.get("product_category") or item.get("category"),
                price=item.get("product_price") or item.get("product_minimum_offer_price") or item.get("price"),
                rating=item.get("product_rating") or item.get("rating"),
                total_reviews=item.get("product_num_reviews") or item.get("review_count"),
                seller_name=item.get("seller_name") or item.get("store_name") or item.get("brand"),
                is_verified_seller=item.get("is_best_seller", True),
                badge="Bestseller" if item.get("is_best_seller") else "Deal" if item.get("product_original_price") else None,
                image_url=_rapidapi_image(item),
                description=item.get("product_description") or item.get("description"),
                trust=item.get("seller_rating") or item.get("trust"),
                brand=item.get("brand"),
            ))
        except ProviderUnavailable:
            continue

    products = _deduplicate(products, limit)
    if not products:
        raise ProviderUnavailable("RapidAPI returned no usable products")
    return products


def fetch_from_dummyjson(query: str = "", limit: int = 11) -> list[dict]:
    try:
        response = httpx.get(
            "https://dummyjson.com/products",
            params={"limit": limit},
            timeout=_timeout(),
        )
        response.raise_for_status()
        items = response.json().get("products")
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    products: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            products.append(_product(
                title=item.get("title"),
                category=item.get("category"),
                price=item.get("price"),
                rating=item.get("rating"),
                total_reviews=len(item.get("reviews") or []) if isinstance(item.get("reviews"), list) else 0,
                seller_name=item.get("brand"),
                is_verified_seller=True,
                badge="Deal" if _number(item.get("discountPercentage"), 0) >= 10 else None,
                image_url=item.get("thumbnail") or (item.get("images") or [None])[0],
                description=item.get("description"),
                brand=item.get("brand"),
            ))
        except ProviderUnavailable:
            continue
    return _deduplicate(products, limit)


def get_live_catalog(query: str = "", limit: int = 11) -> tuple[list[dict], str]:
    for source_name, fetcher in (
        ("ebay", fetch_from_ebay),
        ("rapidapi", fetch_from_rapidapi),
    ):
        try:
            products = fetcher(query, limit)
        except ProviderUnavailable as cause:
            log.warning("product provider %s unavailable, trying next: %s", source_name, str(cause)[:160])
            continue
        if products:
            log.info("product catalog source=%s products=%d", source_name, len(products))
            return products, source_name
        log.warning("product provider %s returned no products, trying next", source_name)

    products = fetch_from_dummyjson(query, limit)
    if products:
        log.info("product catalog source=dummyjson products=%d", len(products))
        return products, "dummyjson"

    fallback, _ = _catalog_defaults()
    log.warning("product providers unavailable, source=hardcoded_fallback products=%d", len(fallback))
    return list(fallback), "hardcoded_fallback"

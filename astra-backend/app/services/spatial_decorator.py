"""Read-only room styling recommendations built from image cues and live catalogue items."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.localization import cross_border_advisory, detect_locale, mirror_language_text
from app.services.shopping_nlu import normalize_shopping_text
from app.services.vision import analyze_room_image

DECOR_SLOTS = {
    "sofa": ("sofa", "couch", "sectional"),
    "rug": ("rug", "carpet", "mat"),
    "curtains": ("curtain", "drape"),
    "lamp": ("lamp", "light", "lighting"),
}


def _model_url(product: Product) -> str | None:
    """Read an optional seller-supplied GLB/GLTF URL from specs, HTTPS only."""
    try:
        value = json.loads(product.specifications or "{}").get("model_url")
        parsed = urlsplit(value) if isinstance(value, str) else None
        host = parsed.hostname if parsed else None
        if not parsed or parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return None
        if host == "localhost" or host.endswith((".local", ".internal")):
            return None
        try:
            if ipaddress.ip_address(host).is_private:
                return None
        except ValueError:
            pass
        return value if parsed.path.lower().endswith((".glb", ".gltf")) else None
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return None


def build_spatial_decor_bundle(
    db: Session, image_bytes: bytes, query: str, locale: str | None, buyer_country: str,
    room_attributes: dict | None = None,
) -> dict:
    """Analyze visible room attributes and return advisory, in-stock decor matches."""
    detected_locale = detect_locale(query)
    active_locale = detected_locale if detected_locale != "en" else detect_locale("", locale)
    fixed_copy = [
        "In-stock catalogue match; check the item's material and dimensions with its seller.",
        "Room dimensions and placement clearances were not measured. Confirm sizes before buying.",
        "Room styling ideas are advisory. No cart, order, wallet, or checkout state was changed.",
        "Image analysis is unavailable; recommendations use your text and catalogue inventory.",
    ]
    localized_copy = mirror_language_text("\n".join(fixed_copy), active_locale).splitlines()
    if len(localized_copy) != len(fixed_copy):
        localized_copy = fixed_copy
    match_reason, dimension_note, response_message, unavailable_note = localized_copy
    visual = room_attributes if room_attributes is not None else analyze_room_image(image_bytes, active_locale)
    normalized_query = normalize_shopping_text(query, active_locale)
    cues = " ".join(str(value) for value in (visual or {}).values())
    search_context = f"{normalized_query} {cues}".strip().lower()
    products: list[dict] = []
    for slot, terms in DECOR_SLOTS.items():
        predicates = [Product.title.ilike(f"%{term}%") | Product.search_terms.ilike(f"%{term}%") | Product.category.ilike(f"%{term}%") for term in terms]
        query_products = db.query(Product).filter(
            Product.listing_status == "active", Product.stock_count > 0, or_(*predicates),
        ).order_by(Product.trust.desc(), Product.rating.desc()).limit(8).all()
        if not query_products:
            continue
        # Favor cue overlap when inventory carries useful descriptive metadata;
        # retain the trusted in-stock ranking when it does not.
        query_products.sort(key=lambda product: sum(
            word in search_context for word in (product.color or "", product.description or "", product.semantic_tags or "")
            if len(word) >= 3
        ), reverse=True)
        product = query_products[0]
        cross_border = cross_border_advisory(product.origin_country, buyer_country, product.price, active_locale)
        products.append({
            "slot": slot,
            "product": {"id": product.id, "title": product.title, "category": product.category,
                        "price": product.price, "image_url": product.image_url,
                        "origin_country": product.origin_country or "PK", "stock_count": product.stock_count,
                        "model_url": _model_url(product)},
            "match_reason": match_reason,
            "cross_border_advisory": cross_border,
        })
    return {
        "locale": active_locale,
        "room_attributes": visual or {
            "wall_color_tones": "", "ambient_lighting": "", "visible_layout": "",
            "furniture_aesthetic": "", "possible_space_constraints": "",
            "confidence_note": unavailable_note,
        },
        "items": products,
        "estimated_bundle_total": round(sum(float(line["product"]["price"]) for line in products), 2),
        "advisory_only": True,
        "review_required": True,
        "dimension_note": dimension_note,
        "message": response_message,
    }

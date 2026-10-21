"""Read-only catalogue based outfit matching with explicit heuristic reasons."""
from typing import Any, Iterable
from app.services.localization import cross_border_advisory, detect_locale, normalize_multilingual_text


_TOP = ("kurta", "shirt", "top", "blouse", "tunic", "tee", "t-shirt", "kameez", "shalwar kameez")
_BOTTOM = ("trouser", "pants", "jeans", "shalwar", "skirt", "bottomwear", "chinos")
_SHOES = ("shoe", "sneaker", "sandal", "heel", "footwear", "loafer", "boot")
_ACCESSORY = ("dupatta", "scarf", "bag", "belt", "accessory", "jewelry", "jewellery")
_FORMAL = ("formal", "wedding", "festive", "embroidered", "party", "occasion")
_CASUAL = ("casual", "everyday", "basic", "relaxed", "tee", "sneaker")
_NEUTRALS = ("black", "white", "cream", "beige", "grey", "gray", "tan", "gold", "navy")
_PATTERNS = ("striped", "stripe", "floral", "printed", "print", "embroidered", "solid", "plaid", "checkered", "geometric")
_COMPLEMENTARY_COLORS = {"red": {"green", "navy", "blue"}, "blue": {"orange", "tan", "cream"},
                         "green": {"pink", "cream", "gold"}, "purple": {"yellow", "gold"},
                         "black": {"white", "cream", "gold"}, "white": {"navy", "black", "red"}}


def _text(product: Any) -> str:
    values = [getattr(product, key, "") or "" for key in
              ("title", "category", "subcategory", "search_terms", "semantic_tags", "quality_tags", "description")]
    return normalize_multilingual_text(" ".join(map(str, values))).lower()


def _color(product: Any) -> str:
    return str(getattr(product, "color", "") or "").strip().lower()


def _formality(product: Any) -> str:
    text = _text(product)
    if any(term in text for term in _FORMAL):
        return "formal"
    if any(term in text for term in _CASUAL):
        return "casual"
    return "versatile"


def _embedding_similarity(left: Any, right: Any) -> float:
    """Use stored pgvector catalogue embeddings as a tie-break when available."""
    try:
        a, b = list(left.embedding), list(right.embedding)
        if not a or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = sum(float(x) ** 2 for x in a) ** 0.5
        norm_b = sum(float(y) ** 2 for y in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _slots(anchor: Any) -> list[tuple[str, tuple[str, ...]]]:
    text = _text(anchor)
    if any(term in text for term in _SHOES):
        return [("top", _TOP), ("bottom", _BOTTOM)]
    if any(term in text for term in _BOTTOM):
        return [("top", _TOP), ("shoes", _SHOES), ("accessory", _ACCESSORY)]
    if any(term in text for term in _TOP):
        return [("bottom", _BOTTOM), ("shoes", _SHOES), ("accessory", _ACCESSORY)]
    return []


_STYLE_CONTEXT = {
    "en": "Mix-and-match suggestions use catalogue attributes; consider local formalwear and modesty preferences.",
    "ur": "South Asian shalwar kameez, dupatta, and modest occasion-wear cues are considered where catalogue data supports them.",
    "roman_urdu": "South Asian shalwar kameez, dupatta aur modest occasion-wear cues catalogue data ke mutabiq shamil hain.",
    "pa": "Punjabi and South Asian formalwear cues are considered when catalogue attributes are available.",
    "ps": "Modest and formal regional wear cues are considered when catalogue attributes are available.",
    "sd": "Sindhi and South Asian occasion-wear cues are considered when catalogue attributes are available.",
    "fa": "Persian modest and formal-wear cues are considered when catalogue attributes are available.",
    "zh": "East Asian apparel and occasion-wear cues are considered when catalogue attributes are available.",
    "ar": "Modest and regional occasion-wear cues are considered when catalogue attributes are available.",
}


def build_outfit_recommendations(anchor: Any, candidates: Iterable[Any], locale: str | None = None,
                                destination_country: str | None = None) -> dict:
    """Rank a single in-stock item for each complementary slot; never writes data."""
    slots = _slots(anchor)
    if not slots:
        return {"outfits": [], "message": "Outfit matching is available for clothing and footwear listings.",
                "style_context": _STYLE_CONTEXT.get(detect_locale("", locale), _STYLE_CONTEXT["en"])}
    candidates = [item for item in candidates if getattr(item, "id", None) != getattr(anchor, "id", None)
                  and getattr(item, "listing_status", "active") == "active"
                  and int(getattr(item, "stock_count", 0) or 0) > 0]
    chosen = []
    anchor_color = _color(anchor)
    anchor_style = _formality(anchor)
    anchor_text = _text(anchor)
    anchor_patterns = [pattern for pattern in _PATTERNS if pattern in anchor_text]
    used_ids = {getattr(anchor, "id", None)}
    for slot, terms in slots:
        matches = [item for item in candidates if getattr(item, "id", None) not in used_ids and any(term in _text(item) for term in terms)]
        if not matches:
            continue

        def rank(item: Any) -> tuple[int, int, int, float, float, str]:
            color = _color(item)
            color_score = 4 if color and anchor_color and any(c in color for c in _COMPLEMENTARY_COLORS.get(anchor_color, set())) else (3 if color and (color == anchor_color or any(n in color for n in _NEUTRALS)) else 0)
            style_score = 2 if _formality(item) == anchor_style and anchor_style != "versatile" else 0
            pattern_score = int(any(pattern in _text(item) for pattern in anchor_patterns))
            return (color_score, style_score, pattern_score, _embedding_similarity(anchor, item),
                    float(getattr(item, "rating", 0) or 0), str(getattr(item, "id", "")))

        match = max(matches, key=rank)
        used_ids.add(getattr(match, "id", None))
        color = _color(match)
        reasons = []
        if color:
            reasons.append(f"Color harmony: {color.title()} with {anchor_color.title()}" if anchor_color else f"Versatile {color.title()} color")
        if anchor_style != "versatile" and _formality(match) == anchor_style:
            reasons.append(f"{anchor_style.title()} style match")
        if any(pattern in _text(match) for pattern in anchor_patterns):
            reasons.append("Pattern match")
        if not reasons:
            reasons.append("Complementary category match")
        chosen.append({
            "slot": slot,
            "product": {"id": match.id, "title": match.title, "category": match.category,
                        "color": color, "price": float(match.base_price), "image_url": match.image_url,
                        "origin_country": getattr(match, "origin_country", None) or "PK",
                        "stock_count": int(match.stock_count)},
            "reasons": reasons,
        })
    if not chosen:
        return {"outfits": [], "message": "No complementary in-stock pieces are available right now.",
                "style_context": _STYLE_CONTEXT.get(detect_locale("", locale), _STYLE_CONTEXT["en"])}
    anchor_item = {"id": anchor.id, "title": anchor.title, "category": anchor.category,
                   "color": anchor_color, "price": float(anchor.base_price), "image_url": anchor.image_url,
                   "origin_country": getattr(anchor, "origin_country", None) or "PK",
                   "stock_count": int(anchor.stock_count)}
    all_items = [anchor_item, *[entry["product"] for entry in chosen]]
    for item in all_items:
        item["cross_border_advisory"] = cross_border_advisory(
            item.get("origin_country"), destination_country, item["price"], locale,
        )
    return {"outfits": [{"items": [{"slot": "main", "product": anchor_item,
                                       "reasons": ["Selected product"]}, *chosen],
                         "estimated_total": round(sum(item["price"] for item in all_items), 2),
                         "advisory_only": True}], "message": "Style and color matches are catalogue-based suggestions.",
            "style_context": _STYLE_CONTEXT.get(detect_locale("", locale), _STYLE_CONTEXT["en"])}

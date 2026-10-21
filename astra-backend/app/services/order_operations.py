"""Read-only order intent parsing and seller-floor bundle quote calculations."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable

from app.services.shopping_nlu import normalize_shopping_text

RETURN_WINDOW_DAYS = 30
DEFAULT_BUNDLE_DISCOUNT = 0.05


@dataclass(frozen=True)
class OrderOperationIntent:
    action: str | None
    product_hint: str | None = None
    request_type: str | None = None


def parse_order_operation(text: str) -> OrderOperationIntent:
    normalized = normalize_shopping_text(text)
    track = any(phrase in normalized for phrase in (
        "where is my order", "track my order", "order status", "mera order kahan",
        "mera order kidhar", "order kahan tak", "pohncha mera order", "pohcha mera order",
    )) or ("order" in normalized and any(word in normalized for word in ("where", "kithay", "kitthe")))
    return_request = any(phrase in normalized for phrase in (
        "return", "wapas", "refund", "exchange",
    )) and any(phrase in normalized for phrase in (
        "order", "item", "product", "shirt", "shoes", "jacket", "pichli", "last",
    ))
    request_type = "exchange" if "exchange" in normalized else "return" if return_request else None
    action = "exchange_request" if request_type == "exchange" else "return_request" if return_request else "track" if track else None
    product_hint = next((term for term in ("shirt", "shoes", "jacket", "dress", "laptop", "phone") if term in normalized), None)
    return OrderOperationIntent(action, product_hint, request_type)


def parse_bundle_request(text: str) -> list[dict[str, int | str]]:
    normalized = normalize_shopping_text(text)
    if not any(signal in normalized for signal in ("bundle", "discount", "aik sath", "saath loon", "together")):
        return []
    aliases = {
        "shirt": ("shirt", "shirts", "qameez", "kameez"),
        "shoes": ("shoe", "shoes", "sneaker", "sneakers"),
        "laptop": ("laptop", "laptops"),
        "phone": ("phone", "phones", "mobile", "mobiles"),
    }
    items = []
    for canonical, words in aliases.items():
        for word in words:
            match = re.search(rf"(?<![a-z0-9])(\d{{1,2}})?\s*{re.escape(word)}(?![a-z0-9])", normalized)
            if match:
                items.append({"product_hint": canonical, "quantity": int(match.group(1) or 1)})
                break
    return items if len(items) >= 2 else []


def return_eligibility(status: str, delivered_at: datetime | None, now: datetime | None = None) -> tuple[bool, str]:
    if status != "delivered" or delivered_at is None:
        return False, "Only delivered orders with a delivery date can be returned."
    delivered = delivered_at.replace(tzinfo=timezone.utc) if delivered_at.tzinfo is None else delivered_at.astimezone(timezone.utc)
    current = now or datetime.now(timezone.utc)
    current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    if delivered < current - timedelta(days=RETURN_WINDOW_DAYS):
        return False, f"The {RETURN_WINDOW_DAYS}-day return window has expired."
    return True, f"Eligible within the {RETURN_WINDOW_DAYS}-day return window."


def calculate_bundle_offer(items: Iterable[dict], discount_rate: float = DEFAULT_BUNDLE_DISCOUNT) -> dict:
    """Apply a modest advisory bundle discount while respecting each seller floor."""
    lines = []
    for item in items:
        quantity = int(item["quantity"])
        price = round(float(item["price"]), 2)
        floor = round(float(item["seller_price_floor"]), 2)
        if quantity < 1 or floor <= 0 or floor > price:
            raise ValueError("Invalid bundle quantity or seller floor")
        offered_unit_price = max(floor, round(price * (1 - discount_rate), 2))
        lines.append({
            "product_id": str(item["product_id"]),
            "title": str(item["title"]),
            "quantity": quantity,
            "list_unit_price": price,
            "seller_floor": floor,
            "offered_unit_price": offered_unit_price,
            "line_total": round(offered_unit_price * quantity, 2),
        })
    if not lines:
        raise ValueError("A bundle must contain at least one item")
    list_total = round(sum(line["list_unit_price"] * line["quantity"] for line in lines), 2)
    offer_total = round(sum(line["line_total"] for line in lines), 2)
    return {
        "items": lines,
        "list_total": list_total,
        "offer_total": offer_total,
        "estimated_savings": round(list_total - offer_total, 2),
        "binding": False,
        "requires_buyer_approval": True,
        "message": "Advisory bundle estimate only. Prices require explicit buyer review and normal consent checkout.",
    }

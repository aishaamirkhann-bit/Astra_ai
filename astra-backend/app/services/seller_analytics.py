"""Read-only, seller-scoped aggregates for the merchant insights dashboard.

This intentionally consumes only listing fields and negotiation aggregates.
The application does not persist search-query or modality events, so this
service reports those panels as unavailable rather than inferring them.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Iterable, Mapping

LOW_STOCK_THRESHOLD = 5
HIGH_DEMAND_NEGOTIATIONS = 2
ACCEPTED_STATUSES = {"accepted", "buyer_approved", "checkout_pending", "completed"}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_seller_insights(
    products: Iterable[Mapping[str, Any]],
    negotiations: Iterable[Mapping[str, Any]],
    paid_order_counts: Mapping[str, int],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a response using only seller-owned listing and negotiation data."""
    now_utc = _as_utc(now or datetime.now(timezone.utc))
    assert now_utc is not None
    cutoff = now_utc - timedelta(days=30)
    product_rows = list(products)
    product_by_id = {str(row["id"]): row for row in product_rows}
    sessions = list(negotiations)
    recent: list[Mapping[str, Any]] = []
    accepted = []
    all_prices: list[float] = []
    by_product: Counter[str] = Counter()
    variants: Counter[tuple[str, str, str]] = Counter()

    for session in sessions:
        product_id = str(session.get("product_id", ""))
        if product_id not in product_by_id:
            continue
        created_at = _as_utc(session.get("created_at"))
        if created_at is None or created_at < cutoff:
            continue
        recent.append(session)
        by_product[product_id] += 1
        color = str(session.get("color") or "").strip()
        size = str(session.get("size") or "").strip()
        if color or size:
            variants[(product_id, color, size)] += 1
        price = session.get("final_price")
        is_accepted = session.get("status") in ACCEPTED_STATUSES and isinstance(price, (int, float)) and price > 0
        if is_accepted:
            accepted.append(session)
            all_prices.append(float(price))

    stock_alerts = []
    inventory_counts = {"active": 0, "low_stock": 0, "out_of_stock": 0}
    for product in product_rows:
        product_id = str(product["id"])
        stock = int(product.get("stock_count") or 0)
        active = product.get("listing_status") == "active"
        if active:
            inventory_counts["active"] += 1
            if stock <= 0:
                inventory_counts["out_of_stock"] += 1
            elif stock <= LOW_STOCK_THRESHOLD:
                inventory_counts["low_stock"] += 1
        demand = by_product[product_id]
        if active and stock <= LOW_STOCK_THRESHOLD:
            if demand >= HIGH_DEMAND_NEGOTIATIONS:
                urgency = "high" if stock == 0 else "watch"
                reason = f"{demand} negotiations in the last 30 days with {stock} units remaining."
            else:
                urgency = "watch"
                reason = f"Only {stock} units remain; review inventory before the next replenishment cycle."
            stock_alerts.append({
                "product_id": product_id,
                "product_title": str(product.get("title", "")),
                "stock_count": stock,
                "negotiations_30d": demand,
                "urgency": urgency,
                "recommendation": reason,
            })
    stock_alerts.sort(key=lambda alert: (alert["urgency"] != "high", alert["stock_count"], -alert["negotiations_30d"]))

    variant_trends = []
    for (product_id, color, size), count in variants.most_common(8):
        product = product_by_id[product_id]
        variant_trends.append({
            "product_id": product_id,
            "product_title": str(product.get("title", "")),
            "color": color or None,
            "size": size or None,
            "negotiations_30d": count,
        })

    price_distribution = {
        "accepted_offer_count": len(all_prices),
        "minimum": round(min(all_prices), 2) if all_prices else None,
        "median": round(median(all_prices), 2) if all_prices else None,
        "maximum": round(max(all_prices), 2) if all_prices else None,
    }
    total_sessions = len(recent)
    linked_orders = sum(max(0, int(paid_order_counts.get(product_id, 0))) for product_id in product_by_id)

    return {
        "window_days": 30,
        "privacy": "Aggregated seller-owned listings and negotiations only; no buyer identifiers or raw messages are returned.",
        "search_trends": {
            "available": False,
            "keywords": [],
            "voice_keywords": [],
            "visual_keywords": [],
            "message": "Search queries and voice/visual modality events are not persisted, so keyword trends are unavailable.",
        },
        "negotiation": {
            "session_count": total_sessions,
            "accepted_offer_count": len(accepted),
            "offer_acceptance_rate": round(len(accepted) / total_sessions, 4) if total_sessions else 0,
            "negotiation_to_paid_order_rate": round(linked_orders / total_sessions, 4) if total_sessions else 0,
            "accepted_price_distribution": price_distribution,
            "pricing_signal": "Descriptive accepted-offer prices only; price elasticity requires impression and controlled price-change conversion data.",
        },
        "variant_demand_30d": variant_trends,
        "inventory": {
            **inventory_counts,
            "low_stock_threshold": LOW_STOCK_THRESHOLD,
            "stock_alerts": stock_alerts,
        },
    }

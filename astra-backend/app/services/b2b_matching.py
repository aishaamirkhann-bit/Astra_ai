from app.models.b2b import B2BBid


def score_vendor_quote(bid: B2BBid, offered_price: float, delivery_days: int) -> float:
    """Deterministic explainable match score; lower price and faster delivery score higher."""
    budget = max(float(bid.target_budget), 0.01)
    target_days = max(int(bid.delivery_days), 1)
    # Meeting the buyer's constraints is a strong fit; quotes better than the
    # target get a small bonus, while prices/timelines beyond target lose score.
    price_score = (budget / max(float(offered_price), 0.01)) / 1.1 * 100.0
    delivery_score = (target_days / max(int(delivery_days), 1)) / 1.1 * 100.0
    price_score = max(0.0, min(100.0, price_score))
    delivery_score = max(0.0, min(100.0, delivery_score))
    return round(max(0.0, min(100.0, price_score * 0.65 + delivery_score * 0.35)), 2)

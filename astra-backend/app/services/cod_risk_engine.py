"""Advisory COD screening; missing signals are reported as unknown."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CodRiskAssessment:
    score: int
    level: str
    factors: list[str]
    signals: dict[str, str | int | float | bool | None]


def score_cod_risk(*, delivered_orders: int, return_count: int, order_total: float,
                   historical_average: float | None, route_risk: str | None,
                   phone_verified: bool | None) -> CodRiskAssessment:
    """Return a transparent 0-100 advisory score using only supplied evidence."""
    score, factors = 20, []  # unknown buyer history starts at a cautious neutral prior
    if delivered_orders == 0:
        score += 15
        factors.append("First-time buyer")
    else:
        rate = return_count / max(delivered_orders, 1)
        score += min(40, round(rate * 80))
        if rate >= 0.25:
            factors.append("Elevated recorded return-request frequency")
    if historical_average and historical_average > 0 and order_total > historical_average * 2:
        score += 20
        factors.append("Order total is over 2x historical average")
    elif historical_average is None:
        factors.append("Historical order average unavailable")
    if route_risk == "high":
        score += 20
        factors.append("High-risk delivery route")
    elif route_risk is None:
        factors.append("Delivery route risk unavailable")
    if phone_verified is False:
        score += 15
        factors.append("Phone verification not recorded")
    elif phone_verified is None:
        factors.append("Phone verification unavailable")
    score = min(100, score)
    level = "HIGH" if score > 70 else "MEDIUM" if score >= 40 else "LOW"
    return CodRiskAssessment(score, level, factors or ["No elevated risk factors recorded"], {
        "delivered_orders": delivered_orders, "recorded_return_requests": return_count,
        "historical_average": historical_average, "route_risk": route_risk,
        "phone_verified": phone_verified,
    })

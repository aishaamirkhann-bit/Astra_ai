"""Live market-price feed.

The deals pipeline historically synthesized static competitor observations.
This module overlays a real external signal — the USD→PKR reference rate
(free, keyless feed) — onto those observations so import-priced catalog
items track actual market movement. If the feed is unreachable the pipeline
degrades gracefully to the previous static multipliers.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deal import MarketPriceHistory
from app.models.product import Product
from app.services.deals_pipeline import SEED_DISCOUNTS

log = logging.getLogger("astra.market_feed")

_COMPETITOR_MULTIPLIERS = [(1.02, "Market A"), (0.99, "Market B"), (1.01, "Market C"), (0.98, "Market D")]

_cache_lock = threading.Lock()
_cached_rate: dict = {"value": None, "fetched_at": None}


def fetch_usd_pkr_rate() -> float | None:
    """Live USD→PKR rate with a TTL cache; None when the feed is unreachable."""
    if not settings.MARKET_FEED_ENABLED:
        return None
    now = datetime.now(timezone.utc)
    with _cache_lock:
        if (
            _cached_rate["value"] is not None
            and _cached_rate["fetched_at"] is not None
            and (now - _cached_rate["fetched_at"]).total_seconds() < settings.MARKET_FEED_TTL_SECONDS
        ):
            return _cached_rate["value"]
    try:
        response = httpx.get(settings.MARKET_FEED_URL, timeout=5.0)
        response.raise_for_status()
        rate = float(response.json()["rates"]["PKR"])
    except Exception as cause:
        log.warning("market feed unavailable, using static observations: %s", str(cause)[:120])
        return None
    with _cache_lock:
        _cached_rate["value"] = rate
        _cached_rate["fetched_at"] = now
    log.info("market feed: USD/PKR = %.2f", rate)
    return rate


def _live_factor(rate: float | None) -> float:
    if rate is None or rate <= 0:
        return 1.0
    raw = rate / settings.MARKET_BASELINE_USD_PKR
    return max(0.95, min(1.05, raw))


def record_market_observations(db: Session) -> int:
    """Append fresh competitor observations for products whose history is stale.

    Throttled to one observation batch per product per
    MARKET_OBSERVATION_INTERVAL_HOURS so the 30-day rolling average drifts
    with the live feed instead of staying frozen at seed values.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.MARKET_OBSERVATION_INTERVAL_HOURS)
    latest = dict(db.execute(
        select(MarketPriceHistory.product_id, func.max(MarketPriceHistory.observed_at))
        .group_by(MarketPriceHistory.product_id)
    ).all())
    factor = _live_factor(fetch_usd_pkr_rate())

    written = 0
    for product in db.scalars(select(Product)).all():
        last = latest.get(product.id)
        if last is not None and (last.tzinfo is None and last.replace(tzinfo=timezone.utc) or last) > cutoff:
            continue
        discount = SEED_DISCOUNTS.get(str(product.badge), 8.0)
        market_average = float(product.base_price) / (1 - discount / 100) * factor
        for multiplier, competitor in _COMPETITOR_MULTIPLIERS:
            db.add(MarketPriceHistory(
                product_id=product.id, competitor=competitor,
                price=round(market_average * multiplier, 2), observed_at=now,
            ))
            written += 1
    if written:
        db.commit()
        log.info("market feed: wrote %d observations (factor %.3f)", written, factor)
    return written

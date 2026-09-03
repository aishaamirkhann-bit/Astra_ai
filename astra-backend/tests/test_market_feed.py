"""Market feed: live factor application, graceful fallback, and throttling."""
from sqlalchemy import func, select

import app.services.market_feed as market_feed
from app.core.database import SessionLocal
from app.models.deal import MarketPriceHistory


def _latest_count(db) -> int:
    return db.scalar(select(func.count(MarketPriceHistory.id))) or 0


def test_live_rate_applies_clamped_factor(monkeypatch) -> None:
    monkeypatch.setattr(market_feed, "fetch_usd_pkr_rate", lambda: 278.5 * 1.20)
    assert market_feed._live_factor(278.5 * 1.20) == 1.05
    monkeypatch.setattr(market_feed, "fetch_usd_pkr_rate", lambda: 278.5 * 0.5)
    assert market_feed._live_factor(278.5 * 0.5) == 0.95
    monkeypatch.setattr(market_feed, "fetch_usd_pkr_rate", lambda: None)
    assert market_feed._live_factor(None) == 1.0


def test_record_observations_writes_and_throttles(monkeypatch) -> None:
    monkeypatch.setattr(market_feed, "fetch_usd_pkr_rate", lambda: None)
    with SessionLocal() as db:
        before = _latest_count(db)
        written = market_feed.record_market_observations(db)
        after = _latest_count(db)
        assert after == before + written
        # Second call within the interval is throttled.
        assert market_feed.record_market_observations(db) == 0


def test_feed_failure_falls_back_to_static_factor(monkeypatch) -> None:
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(market_feed.settings, "MARKET_FEED_TTL_SECONDS", -1)
    monkeypatch.setattr(market_feed, "_cached_rate", {"value": None, "fetched_at": None})
    # fetch must never raise even when httpx would.
    monkeypatch.setattr(market_feed.httpx, "get", boom)
    assert market_feed.fetch_usd_pkr_rate() is None

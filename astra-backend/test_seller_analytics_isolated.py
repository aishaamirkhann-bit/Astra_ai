from datetime import datetime, timedelta, timezone

from app.services.seller_analytics import build_seller_insights


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def test_analytics_aggregates_only_seller_listings_and_exposes_no_buyer_data():
    products = [
        {"id": "owned", "title": "Blue Shirt", "price": 3200, "stock_count": 2, "listing_status": "active"},
        {"id": "inactive", "title": "Hidden Shirt", "price": 3000, "stock_count": 1, "listing_status": "inactive"},
    ]
    negotiations = [
        {"product_id": "owned", "status": "buyer_approved", "final_price": 2800, "created_at": NOW - timedelta(days=2), "size": "M", "color": "Blue", "buyer_email": "private@example.com", "raw_message": "private text"},
        {"product_id": "owned", "status": "active", "final_price": None, "created_at": NOW - timedelta(days=1), "size": "M", "color": "Blue"},
        {"product_id": "foreign", "status": "buyer_approved", "final_price": 100, "created_at": NOW, "size": "S", "color": "Red"},
    ]

    result = build_seller_insights(products, negotiations, {"owned": 1}, now=NOW)

    assert result["negotiation"]["session_count"] == 2
    assert result["negotiation"]["accepted_offer_count"] == 1
    assert result["negotiation"]["offer_acceptance_rate"] == 0.5
    assert result["negotiation"]["accepted_price_distribution"] == {
        "accepted_offer_count": 1, "minimum": 2800.0, "median": 2800.0, "maximum": 2800.0,
    }
    assert result["variant_demand_30d"] == [{
        "product_id": "owned", "product_title": "Blue Shirt", "color": "Blue", "size": "M", "negotiations_30d": 2,
    }]
    assert result["search_trends"]["available"] is False
    assert result["search_trends"]["keywords"] == []
    assert result["inventory"]["active"] == 1
    assert result["inventory"]["stock_alerts"][0]["product_id"] == "owned"
    serialized = repr(result)
    assert "private@example.com" not in serialized
    assert "private text" not in serialized
    assert "buyer_email" not in serialized


def test_stock_alerts_include_high_demand_and_do_not_invent_search_metrics():
    result = build_seller_insights(
        [{"id": "coat", "title": "Winter Coat", "stock_count": 0, "listing_status": "active"}],
        [
            {"product_id": "coat", "status": "active", "created_at": NOW, "color": "Black", "size": "L"},
            {"product_id": "coat", "status": "rejected", "created_at": NOW, "color": "Black", "size": "L"},
        ],
        {}, now=NOW,
    )

    alert = result["inventory"]["stock_alerts"][0]
    assert alert["urgency"] == "high"
    assert alert["stock_count"] == 0
    assert alert["negotiations_30d"] == 2
    assert result["search_trends"]["voice_keywords"] == []
    assert result["search_trends"]["visual_keywords"] == []


def test_expired_window_negotiations_are_not_counted():
    result = build_seller_insights(
        [{"id": "shoe", "title": "Shoe", "stock_count": 10, "listing_status": "active"}],
        [{"product_id": "shoe", "status": "buyer_approved", "final_price": 100, "created_at": NOW - timedelta(days=31)}],
        {}, now=NOW,
    )
    assert result["negotiation"]["session_count"] == 0
    assert result["negotiation"]["accepted_offer_count"] == 0
    assert result["variant_demand_30d"] == []

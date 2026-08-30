from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.deal import MarketPriceHistory
from app.models.trust import SellerVerification, TrustAuditLog

client = TestClient(app)


def test_dashboard_stats_are_database_backed() -> None:
    response = client.get("/api/v1/astra-check/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_verified_sellers"] > 0
    assert 0 <= payload["average_platform_trust_index"] <= 100
    assert payload["real_time_scans_active"] > 0


def test_inspection_calculates_weighted_score_and_writes_audit() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    response = client.post("/api/v1/astra-check/inspect", json={"query": deal["slug"]})
    assert response.status_code == 200
    result = response.json()
    expected = round(0.4 * result["seller_score"] + 0.4 * result["review_sentiment_score"] + 0.2 * result["price_stability_score"], 2)
    assert result["trust_score"] == expected
    assert result["price_history"]
    assert result["external_audit_id"]
    assert isinstance(result["price_anomaly_detected"], bool)
    with SessionLocal() as db:
        assert db.get(TrustAuditLog, result["audit_id"]) is not None


def test_low_override_unlists_deal_and_admin_approval_restores_it() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    with SessionLocal() as db:
        product = db.get(Product, deal["slug"])
        original_score = product.trust

    lowered = client.post("/api/v1/astra-check/override", json={
        "product_id": deal["slug"], "score": 50, "reason": "Automated test anomaly",
    })
    assert lowered.status_code == 200
    assert lowered.json()["deal_active"] is False
    active_ids = {item["id"] for item in client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]}
    assert deal["id"] not in active_ids

    approved = client.post("/api/v1/astra-check/actions/approved_for_deals", json={
        "product_id": deal["slug"], "reason": "Automated test approval",
    })
    assert approved.status_code == 200
    assert approved.json()["deal_active"] is True

    client.post("/api/v1/astra-check/actions/manual_override", json={
        "product_id": deal["slug"], "score": original_score, "reason": "Restore test score",
    })


def test_flag_action_persists_seller_verification_state() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    flagged = client.post("/api/v1/astra-check/actions/flagged", json={
        "product_id": deal["slug"], "reason": "Suspicious review pattern",
    })
    assert flagged.status_code == 200
    with SessionLocal() as db:
        product = db.get(Product, deal["slug"])
        verification = db.get(SellerVerification, product.seller_id)
        assert verification.is_flagged is True
        verification.is_flagged = False
        db.commit()
    client.post("/api/v1/astra-check/actions/approved_for_deals", json={
        "product_id": deal["slug"], "reason": "Restore after test",
    })


def test_seller_profile_returns_verification_history() -> None:
    inspection = client.post("/api/v1/astra-check/inspect", json={"query": "TechBazaar Official"}).json()
    response = client.get(f"/api/v1/astra-check/seller/{inspection['seller']['seller_id']}")
    assert response.status_code == 200
    profile = response.json()
    assert profile["verification"]["business_name"]
    assert profile["verification"]["verification_status"] in {"pending", "verified", "rejected", "suspended"}
    assert profile["audit_history"]


def test_price_below_half_market_average_gets_fifteen_point_penalty() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    with SessionLocal() as db:
        product = db.get(Product, deal["slug"])
        original_price = product.base_price
        history = db.query(MarketPriceHistory).filter(MarketPriceHistory.product_id == product.id).all()
        market_average = sum(point.price for point in history) / len(history)
        product.base_price = market_average * 0.4
        db.commit()
    result = client.post("/api/v1/astra-check/inspect", json={"query": deal["slug"]}).json()
    raw_score = round(0.4 * result["seller_score"] + 0.4 * result["review_sentiment_score"] + 0.2 * result["price_stability_score"], 2)
    assert result["price_anomaly_detected"] is True
    assert result["trust_score"] == max(0, round(raw_score - 15, 2))
    assert "Price_Anomaly_Warning" in result["reasoning_summary"]
    with SessionLocal() as db:
        db.get(Product, deal["slug"]).base_price = original_price
        db.commit()
    client.post("/api/v1/astra-check/inspect", json={"query": deal["slug"]})
    client.post("/api/v1/astra-check/actions/approved_for_deals", json={"product_id": deal["slug"], "reason": "Restore after anomaly test"})

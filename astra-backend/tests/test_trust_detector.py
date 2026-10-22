from datetime import datetime, timezone, timedelta

from app.core.database import SessionLocal
from app.models.order import Order
from app.models.product import Product
from app.models.wallet import UserWallet
from app.services.trust_detector import analyze_photo_evidence, analyze_reviews, build_trust_assessment


def test_consistent_review_set_scores_above_mismatched_bot_pattern():
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    authentic = [
        {"rating": 5, "text": "Excellent quality and comfortable fit", "created_at": now},
        {"rating": 4, "text": "Good fabric, would recommend", "created_at": now + timedelta(hours=2)},
        {"rating": 2, "text": "Bad quality and damaged stitching", "created_at": now + timedelta(hours=8)},
    ]
    suspicious = [
        {"rating": 5, "text": "Bad broken product", "created_at": now},
        {"rating": 5, "text": "Good product", "created_at": now + timedelta(minutes=1)},
        {"rating": 5, "text": "Good product", "created_at": now + timedelta(minutes=2)},
    ]
    clean_score = analyze_reviews(authentic)
    suspicious_score = analyze_reviews(suspicious)
    assert clean_score["score"] > suspicious_score["score"]
    assert suspicious_score["velocity_flag"] is True
    assert suspicious_score["duplicate_rate"] > 0
    assert suspicious_score["mismatch_rate"] > 0


def test_zero_review_photo_evidence_uses_limited_confidence_fallback():
    result = build_trust_assessment(reviews=[], photos=[], seller_score=88, seller_verified=True)
    assert result["confidence"] == "low"
    assert result["verified"] is False
    assert result["grade"] == "Limited evidence"
    assert result["evidence"]["reviews"]["available"] is False
    assert result["evidence"]["photos"]["available"] is False


def test_photo_mismatch_and_duplicate_flags_lower_photo_score():
    result = analyze_photo_evidence([
        {"matches_listing": False, "content_hash": "same", "width": 800, "height": 800},
        {"matches_listing": True, "content_hash": "same", "width": 800, "height": 800},
    ])
    assert result["score"] < 100
    assert result["duplicate_rate"] > 0
    assert result["match_rate"] == 0.5


def test_trust_endpoint_does_not_mutate_catalogue_orders_or_wallet(auth_client, demo_user_id):
    with SessionLocal() as db:
        product = db.query(Product).filter(Product.listing_status == "active").first()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).first()
        assert product and wallet
        product_id = product.id
        product_state = (product.base_price, product.trust, product.stock_count, product.listing_status)
        product_count = db.query(Product).count()
        order_state = [(row.id, row.status.value, row.price) for row in db.query(Order).order_by(Order.id).all()]
        wallet_balance = wallet.available_balance

    response = auth_client.get(f"/api/v1/products/{product_id}/trust-score")
    assert response.status_code == 200, response.text
    assert response.json()["advisory_only"] is True
    with SessionLocal() as db:
        current_product = db.get(Product, product_id)
        assert (current_product.base_price, current_product.trust, current_product.stock_count, current_product.listing_status) == product_state
        assert db.query(Product).count() == product_count
        assert [(row.id, row.status.value, row.price) for row in db.query(Order).order_by(Order.id).all()] == order_state
        assert db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one().available_balance == wallet_balance

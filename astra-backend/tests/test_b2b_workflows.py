from contextlib import ExitStack
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.b2b import B2BBid, DistributionLedger, VendorQuote, VendorSubscription
from app.models.user import User


def _create_user(role: str) -> User:
    user = User(
        name=f"B2B test {role}",
        email=f"b2b-{role}-{uuid4().hex}@example.test",
        hashed_password="not-used-by-token-tests",
        role=role,
        is_active=True,
    )
    with SessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _client(user: User) -> TestClient:
    token = create_access_token(str(user.id), {"role": user.role})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_buyer_can_award_one_of_multiple_supplier_quotes_without_creating_payment():
    buyer = _create_user("buyer")
    supplier_a = _create_user("seller")
    supplier_b = _create_user("seller")
    bid_id = None
    try:
        with ExitStack() as stack:
            buyer_client = stack.enter_context(_client(buyer))
            supplier_a_client = stack.enter_context(_client(supplier_a))
            supplier_b_client = stack.enter_context(_client(supplier_b))
            bid_response = buyer_client.post("/api/v1/b2b/requests", json={
                "title": "Wholesale shirts", "category": "Apparel", "quantity": 100,
                "target_budget": 20000, "delivery_days": 14,
            })
            assert bid_response.status_code == 201, bid_response.text
            bid_id = bid_response.json()["id"]

            first = supplier_a_client.post("/api/v1/b2b/place-bid", json={
                "bid_id": bid_id, "offered_price": 10000, "delivery_days": 10, "is_featured": False,
            })
            second = supplier_b_client.post("/api/v1/b2b/place-bid", json={
                "bid_id": bid_id, "offered_price": 11000, "delivery_days": 8, "is_featured": True,
            })
            assert first.status_code == 201, first.text
            assert second.status_code == 201, second.text
            first_quote = first.json()
            assert first_quote["commission_rate"] == 0.01
            assert first_quote["commission_amount"] == 100
            assert first_quote["vendor_net_payout"] == 9900
            assert second.json()["commission_rate"] == 0.02
            assert second.json()["commission_amount"] == 220
            assert second.json()["vendor_net_payout"] == 10780

            duplicate = supplier_a_client.post("/api/v1/b2b/place-bid", json={
                "bid_id": bid_id, "offered_price": 10500, "delivery_days": 9, "is_featured": False,
            })
            assert duplicate.status_code == 409

            supplier_a_quotes = supplier_a_client.get("/api/v1/b2b/vendor/quotes")
            supplier_b_quotes = supplier_b_client.get("/api/v1/b2b/vendor/quotes")
            assert supplier_a_quotes.status_code == supplier_b_quotes.status_code == 200
            assert [quote["id"] for quote in supplier_a_quotes.json()] == [first.json()["id"]]
            assert [quote["id"] for quote in supplier_b_quotes.json()] == [second.json()["id"]]

            compared = buyer_client.get(f"/api/v1/b2b/requests/{bid_id}/quotes")
            assert compared.status_code == 200
            assert {quote["id"] for quote in compared.json()} == {first_quote["id"], second.json()["id"]}

            supplier_requests = supplier_a_client.get("/api/v1/b2b/requests")
            assert supplier_requests.status_code == 200
            visible_bid = next(item for item in supplier_requests.json() if item["id"] == bid_id)
            assert visible_bid["quotes"] == []
            assert supplier_a_client.get(f"/api/v1/b2b/requests/{bid_id}/quotes").status_code == 403

            awarded = buyer_client.post(f"/api/v1/b2b/requests/{bid_id}/award/{first_quote['id']}")
            assert awarded.status_code == 200, awarded.text
            result = awarded.json()
            assert result["status"] == "awarded"
            assert result["bid_status"] == "awarded"
            assert result["commission_rate"] == 0.01
            assert result["commission_amount"] == 100
            assert result["vendor_net_payout"] == 9900
            assert result["order_created"] is False
            assert result["payment_processed"] is False

        with SessionLocal() as db:
            bid = db.get(B2BBid, bid_id)
            quotes = db.query(VendorQuote).filter(VendorQuote.bid_id == bid_id).all()
            assert bid.status == "awarded"
            assert sorted(quote.status for quote in quotes) == ["awarded", "declined"]

        with _client(supplier_a) as supplier_client:
            forbidden = supplier_client.post(f"/api/v1/b2b/requests/{bid_id}/award/{first_quote['id']}")
            assert forbidden.status_code == 403

        admin = _create_user("admin")
        try:
            with _client(admin) as admin_client:
                assert admin_client.post(f"/api/v1/b2b/requests/{bid_id}/award/{first_quote['id']}").status_code == 403
                assert admin_client.get(f"/api/v1/b2b/requests/{bid_id}/quotes").status_code == 403
        finally:
            with SessionLocal() as db:
                db.delete(db.get(User, admin.id))
                db.commit()
    finally:
        with SessionLocal() as db:
            if bid_id is not None:
                db.query(VendorQuote).filter(VendorQuote.bid_id == bid_id).delete(synchronize_session=False)
                db.query(B2BBid).filter(B2BBid.id == bid_id).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_([buyer.id, supplier_a.id, supplier_b.id])).delete(synchronize_session=False)
            db.commit()


def test_basic_supplier_monthly_limit_counts_awarded_quotes_too():
    buyer = _create_user("buyer")
    supplier = _create_user("seller")
    bid_ids = []
    try:
        with SessionLocal() as db:
            for index in range(6):
                bid = B2BBid(
                    buyer_id=buyer.id, title=f"Quota test request {index}", category="Apparel",
                    quantity=10, target_budget=10000, delivery_days=10,
                    status="awarded" if index < 5 else "open",
                )
                db.add(bid)
                db.flush()
                bid_ids.append(bid.id)
                if index < 5:
                    db.add(VendorQuote(
                        bid_id=bid.id, vendor_id=supplier.id, offered_price=10000,
                        delivery_days=10, ai_match_score=50, commission_rate=0.01,
                        commission_amount=100, vendor_net_payout=9900, status="awarded",
                    ))
            db.commit()

        with _client(supplier) as client:
            selected = client.post("/api/v1/subscriptions/select?tier=Pro")
            assert selected.status_code == 201
            assert selected.json()["status"] == "pending_payment"
            response = client.post("/api/v1/b2b/place-bid", json={
                "bid_id": bid_ids[-1], "offered_price": 10000, "delivery_days": 10, "is_featured": False,
            })
        assert response.status_code == 403
        assert "five supplier quotes per month" in response.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.query(VendorQuote).filter(VendorQuote.bid_id.in_(bid_ids)).delete(synchronize_session=False)
            db.query(B2BBid).filter(B2BBid.id.in_(bid_ids)).delete(synchronize_session=False)
            db.query(VendorSubscription).filter(VendorSubscription.vendor_id == supplier.id).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_([buyer.id, supplier.id])).delete(synchronize_session=False)
            db.commit()


def test_khata_alert_is_scoped_to_retailer_distributor_and_admin():
    retailer = _create_user("buyer")
    outsider = _create_user("buyer")
    distributor = _create_user("seller")
    unrelated_supplier = _create_user("seller")
    administrator = _create_user("admin")
    try:
        with SessionLocal() as db:
            db.add(DistributionLedger(
                distributor_id=distributor.id, retailer_id=retailer.id, entry_type="sale",
                platform_commission_rate=0.015, commission_amount=15, credit_amount=0,
                khata_amount=0, credit_limit=1000, reference="audit relationship",
            ))
            db.commit()
        with ExitStack() as stack:
            retailer_client = stack.enter_context(_client(retailer))
            distributor_client = stack.enter_context(_client(distributor))
            outsider_client = stack.enter_context(_client(outsider))
            unrelated_client = stack.enter_context(_client(unrelated_supplier))
            admin_client = stack.enter_context(_client(administrator))
            path = f"/api/v1/distribution/khata-alert/{retailer.id}"
            assert retailer_client.get(path).status_code == 200
            assert distributor_client.get(path).status_code == 200
            assert outsider_client.get(path).status_code == 403
            assert unrelated_client.get(path).status_code == 403
            assert admin_client.get(path).status_code == 200
    finally:
        with SessionLocal() as db:
            db.query(DistributionLedger).filter(
                DistributionLedger.retailer_id == retailer.id,
                DistributionLedger.distributor_id == distributor.id,
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_([
                retailer.id, outsider.id, distributor.id, unrelated_supplier.id, administrator.id,
            ])).delete(synchronize_session=False)
            db.commit()

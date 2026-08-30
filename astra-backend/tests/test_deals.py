from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.cart import CartItem
from app.models.deal import Deal, DealReservation
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, WalletTransaction

client = TestClient(app)


def test_deals_match_frontend_card_contract() -> None:
    response = client.get("/api/v1/deals")

    assert response.status_code == 200
    payload = response.json()
    deals = payload["items"]
    assert payload["total"] == len(deals)
    assert deals
    assert {
        "slug",
        "name",
        "price_display",
        "price",
        "market_price",
        "discount_percent",
        "rating",
        "tag",
        "trust",
        "seller",
        "category",
        "image",
    } <= deals[0].keys()
    assert all(deal["discount_percent"] >= 15 for deal in deals)
    assert all(deal["trust"]["overall"] >= 75 for deal in deals)
    assert all(deal["price"] < deal["market_price"] for deal in deals)


def test_deals_can_filter_category_and_sort_by_trust() -> None:
    response = client.get("/api/v1/deals", params={"category": "Tech", "sort_by": "top_trust"})

    assert response.status_code == 200
    deals = response.json()["items"]
    assert all(deal["category"] == "Tech" for deal in deals)
    scores = [deal["trust"]["overall"] for deal in deals]
    assert scores == sorted(scores, reverse=True)


def test_deal_details_include_history_and_variants() -> None:
    deal_id = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]["id"]
    response = client.get(f"/api/v1/deals/{deal_id}/details")

    assert response.status_code == 200
    assert response.json()["price_history"]
    assert response.json()["sizes"]


def test_reservation_rejects_quantity_above_inventory() -> None:
    deals = client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    deal = next(item for item in deals if item["stock_remaining"] < 10)
    response = client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 10})

    assert response.status_code == 409


def test_cart_is_persisted_for_current_user() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    response = client.post("/api/v1/ai-assistant/add-to-cart", json={
        "product_slug": deal["slug"], "quantity": 2, "size": "Standard", "color": "Graphite",
    })
    assert response.status_code == 200
    assert response.json()["cart_total_quantity"] >= 2
    cart = client.get("/api/v1/ai-assistant/cart")
    assert cart.status_code == 200
    assert any(item["product_slug"] == deal["slug"] for item in cart.json()["items"])

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        db.query(CartItem).filter(
            CartItem.user_id == user.id, CartItem.product_id == deal["slug"],
            CartItem.size == "Standard", CartItem.color == "Graphite",
        ).delete()
        db.commit()


def test_deal_reservation_creates_approval_order_and_cancel_releases_stock() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    deal = next(item for item in deal if item["stock_remaining"] >= 1)
    before = deal["stock_remaining"]
    reserved = client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1})
    assert reserved.status_code == 200
    payload = reserved.json()
    assert payload["order_ref"].startswith("ORD-")

    cancelled = client.post("/api/v1/approval/cancel", json={"order_ref": payload["order_ref"]})
    assert cancelled.status_code == 200
    refreshed = client.get(f"/api/v1/deals/{deal['id']}/details").json()
    assert refreshed["stock_remaining"] == before

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == payload["order_ref"]).first()
        reservation_id = order.reservation_id
        db.delete(order)
        db.query(DealReservation).filter(DealReservation.id == reservation_id).delete()
        db.commit()


def test_concurrent_reservations_cannot_oversell() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 1}).json()["items"][0]
    with SessionLocal() as db:
        deal_row = db.query(Deal).filter(Deal.id == deal["id"]).first()
        product = db.query(Product).filter(Product.id == deal_row.product_id).first()
        original_stock = product.stock_count
        product.stock_count = 1
        deal_row.stock_remaining = 1
        db.commit()

    def reserve_once():
        return client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: reserve_once(), range(2)))
    statuses = sorted(response.status_code for response in responses)
    assert statuses[0] == 200
    assert statuses[1] in {404, 409, 423}

    successful = next(response.json() for response in responses if response.status_code == 200)
    client.post("/api/v1/approval/cancel", json={"order_ref": successful["order_ref"]})
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == successful["order_ref"]).first()
        reservation_id = order.reservation_id
        deal_row = db.query(Deal).filter(Deal.id == deal["id"]).first()
        product = db.query(Product).filter(Product.id == deal_row.product_id).first()
        product.stock_count = original_stock
        deal_row.stock_remaining = original_stock
        db.delete(order)
        db.query(DealReservation).filter(DealReservation.id == reservation_id).delete()
        db.commit()


def test_approved_deal_is_listed_and_can_be_reversed() -> None:
    deal = client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    balance = client.get("/api/v1/wallet").json()["available_balance"]
    deal = next(item for item in deal if item["stock_remaining"] >= 1 and item["price"] <= balance)
    before = deal["stock_remaining"]
    reserved = client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1}).json()
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == reserved["order_ref"]).first()
        amount = order.price
    blocked = client.post("/api/v1/approval/approve", json={"order_ref": reserved["order_ref"]})
    if blocked.status_code == 428:
        consent = client.post("/api/v1/wallet/authorize-consent", json={
            "amount": amount, "auth_method": "Voice", "order_ref": reserved["order_ref"],
            "voice_transcript": f"I authorize payment of Rs. {int(amount)}",
        }).json()
        approved = client.post("/api/v1/approval/approve", json={"order_ref": reserved["order_ref"], "consent_id": consent["consent_id"]})
    else:
        approved = blocked
    assert approved.status_code == 200
    orders = client.get("/api/v1/orders")
    assert orders.status_code == 200
    assert any(order["order_ref"] == reserved["order_ref"] and order["status"] == "reversal_window_open" for order in orders.json())

    reversed_order = client.post(f"/api/v1/orders/{reserved['order_ref']}/reverse")
    assert reversed_order.status_code == 200
    assert client.get(f"/api/v1/deals/{deal['id']}/details").json()["stock_remaining"] == before

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == reserved["order_ref"]).first()
        reservation_id = order.reservation_id
        db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id).delete()
        db.query(FinancialConsentLog).filter(FinancialConsentLog.reference_order_id == order.id).delete()
        db.delete(order)
        db.query(DealReservation).filter(DealReservation.id == reservation_id).delete()
        db.commit()

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_deals_match_frontend_card_contract() -> None:
    response = client.get("/api/v1/deals")

    assert response.status_code == 200
    payload = response.json()
    deals = payload["items"]
    assert payload["total"] == 6
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

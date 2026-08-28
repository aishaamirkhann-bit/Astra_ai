import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import app


client = TestClient(app)


def test_text_search_returns_ui_product_shape() -> None:
    response = client.post("/api/v1/explore/search", data={"text_query": "gaming laptop"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_results"] >= 1
    assert payload["items"][0]["title"] == "Lenovo IdeaPad Slim 5"
    assert payload["items"][0]["formatted_price"] == "Rs. 149,999"


def test_text_search_returns_only_relevant_products() -> None:
    response = client.post("/api/v1/explore/search", data={"text_query": "noise cancelling headphones"})
    assert response.status_code == 200
    assert response.json()["total_results"] == 2
    assert all(item["category"] == "Audio & Wearables" for item in response.json()["items"])


def test_unknown_search_returns_no_products() -> None:
    response = client.post("/api/v1/explore/search", data={"text_query": "professional drone telescope"})
    assert response.status_code == 200
    assert response.json()["total_results"] == 0


def test_product_detail_endpoint_returns_product() -> None:
    response = client.get("/api/v1/explore/products/lenovo-ideapad-slim-5")
    assert response.status_code == 200
    assert response.json()["title"] == "Lenovo IdeaPad Slim 5"
    assert response.json()["trust"] == 91


def test_products_endpoint_returns_database_catalog() -> None:
    response = client.get("/api/v1/explore/products")
    assert response.status_code == 200
    assert len(response.json()) == 7
    assert response.json()[1]["id"] == "lenovo-ideapad-slim-5"


def test_categories_are_mapped_to_products() -> None:
    response = client.get("/api/v1/explore/categories")
    assert response.status_code == 200
    categories = {item["name"]: item["product_count"] for item in response.json()}
    assert categories["Mobiles"] == 2
    assert categories["Laptops & Computers"] == 2
    assert categories["Audio & Wearables"] == 3
    assert categories["Makeup & Beauty"] == 0
    assert categories["Households"] == 0


def test_category_products_endpoint_filters_in_database() -> None:
    response = client.get("/api/v1/explore/categories/mobiles/products?min_price=120000&max_price=130000")
    assert response.status_code == 200
    assert response.json()["total_results"] == 1
    assert response.json()["items"][0]["id"] == "xiaomi-14-civi"


def test_wallet_endpoint_returns_available_balance() -> None:
    response = client.get("/api/v1/explore/wallet")
    assert response.status_code == 200
    assert response.json() == {"available_balance": 25000, "formatted_balance": "Rs. 25,000"}


def test_budget_recommendations_use_wallet_balance() -> None:
    response = client.post(
        "/api/v1/explore/budget-recommendations",
        data={"text_query": "headphones", "category": "All", "min_price": "0", "max_price": "500000"},
    )
    assert response.status_code == 200
    assert response.json()["available_balance"] == 25000
    assert response.json()["total_results"] == 1
    assert response.json()["items"][0]["id"] == "anker-soundcore-q45"


def test_missing_product_returns_not_found() -> None:
    response = client.get("/api/v1/explore/products/does-not-exist")
    assert response.status_code == 404


def test_roman_urdu_budget_is_applied() -> None:
    response = client.post(
        "/api/v1/explore/search",
        data={"text_query": "gaming laptop 200k ke under", "category": "Laptops & Computers"},
    )
    assert response.status_code == 200
    assert all(item["price"] <= 200000 for item in response.json()["items"])


def test_semantic_tag_and_price_filters_are_strict() -> None:
    response = client.post(
        "/api/v1/explore/search",
        data={"semantic_tags": "Bestseller", "max_price": "300000"},
    )
    assert response.status_code == 200
    assert all("Bestseller" in item["semantic_tags"] and item["price"] <= 300000 for item in response.json()["items"])


def test_voice_requires_audio_file() -> None:
    response = client.post("/api/v1/explore/search", data={"query_type": "voice"})
    assert response.status_code == 422


def test_voice_search_returns_resolved_query() -> None:
    response = client.post(
        "/api/v1/explore/search",
        data={"query_type": "voice"},
        files={"audio_file": ("search.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["query"] == "gaming laptop 200k ke under"


def test_invalid_query_type_returns_validation_error() -> None:
    response = client.post("/api/v1/explore/search", data={"query_type": "video"})
    assert response.status_code == 422


def test_image_search_accepts_image_upload() -> None:
    response = client.post(
        "/api/v1/explore/search",
        data={"query_type": "image"},
        files={"image_file": ("phone.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["total_results"] >= 1


def test_image_search_uses_filename_category_hint() -> None:
    response = client.post(
        "/api/v1/explore/search",
        data={"query_type": "image"},
        files={"image_file": ("headphones-product.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["query"] == "headphones audio"
    assert all(item["category"] == "Audio & Wearables" for item in response.json()["items"])

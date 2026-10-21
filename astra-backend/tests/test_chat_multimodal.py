import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.chat import ChatConversation, ChatMessage
from app.models.product import Product
from app.services.vision import ChatVisionResult


@pytest.fixture
def created_chat_conversations():
    conversation_ids: list[int] = []
    yield conversation_ids
    if conversation_ids:
        with SessionLocal() as db:
            db.query(ChatMessage).filter(ChatMessage.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
            db.query(ChatConversation).filter(ChatConversation.id.in_(conversation_ids)).delete(synchronize_session=False)
            db.commit()


def test_multimodal_chat_returns_text_and_matching_product_cards(auth_client: TestClient, created_chat_conversations: list[int]) -> None:
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "Show me laptops 200k ke under"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["conversation_id"]
    assert payload["reply_text"]
    assert payload["products"]
    assert all(item["slug"] and item["price"] <= 200_000 for item in payload["products"])


def test_chat_greeting_returns_warm_roman_urdu_without_catalog_noise(
    auth_client: TestClient,
    created_chat_conversations: list[int],
) -> None:
    response = auth_client.post("/api/v1/chat/message", data={"message": "salaam"})

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["reply_text"] == "Walaikum Assalam! Astra AI mein aapka khushamdeed. Main aapki kya madad karoon?"
    assert payload["products"] == []


def test_multimodal_chat_analyzes_attached_image(
    auth_client: TestClient,
    monkeypatch,
    created_chat_conversations: list[int],
) -> None:
    def describe_image(image_bytes: bytes, content_type: str, prompt: str) -> ChatVisionResult:
        assert image_bytes
        assert content_type == "image/png"
        assert prompt == "How can I decorate this room?"
        return ChatVisionResult(
            status="analyzed",
            answer="The room has neutral walls and open floor space.",
        )

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.describe_image_for_chat",
        describe_image,
    )
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "How can I decorate this room?"},
        files={"image": ("room.png", b"test-image-content", "image/png")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["vision_status"] == "analyzed"
    assert "neutral walls" in payload["reply_text"]
    assert payload["products"] == []
    history = auth_client.get("/api/v1/chat/history")
    conversation = next(item for item in history.json() if item["id"] == payload["conversation_id"])
    assert conversation["messages"][-2]["card_type"] == "image_attachment"


def test_multimodal_chat_reports_missing_vision_configuration(
    auth_client: TestClient,
    monkeypatch,
    created_chat_conversations: list[int],
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.describe_image_for_chat",
        lambda *_args: ChatVisionResult(status="not_configured"),
    )
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "What is this?"},
        files={"image": ("photo.png", b"image-content", "image/png")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["vision_status"] == "not_configured"
    assert "VISION_API_KEY" in payload["reply_text"]


def test_multimodal_chat_reports_provider_failure(
    auth_client: TestClient,
    monkeypatch,
    created_chat_conversations: list[int],
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.describe_image_for_chat",
        lambda *_args: ChatVisionResult(status="provider_error"),
    )
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "What is this?"},
        files={"image": ("photo.png", b"image-content", "image/png")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["vision_status"] == "provider_error"
    assert "couldn't analyze it right now" in payload["reply_text"]


def test_multimodal_chat_rejects_unsupported_image_types(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "What is this?"},
        files={"image": ("photo.gif", b"image-content", "image/gif")},
    )

    assert response.status_code == 415


def test_multimodal_chat_rejects_images_larger_than_eight_megabytes(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/chat/message",
        data={"message": "Describe this"},
        files={"image": ("large.png", b"x" * (8 * 1024 * 1024 + 1), "image/png")},
    )

    assert response.status_code == 413


@pytest.mark.parametrize(
    ("query", "expected_categories", "max_price"),
    [
        ("Show me laptops 200k ke under", {"Laptops & Computers"}, 200_000),
        ("mujhe dresses dikhao", {"Dresses & Fashion", "Clothing & Fashion"}, None),
        ("makeup chahiye", {"Makeup & Beauty"}, None),
        ("furniture", {"Furniture"}, None),
        ("wallpapers dikhao", {"Wallpapers"}, None),
        ("dresses under 5000", {"Dresses & Fashion", "Clothing & Fashion"}, 5_000),
        ("makeup jo 3000 mein ho", {"Makeup & Beauty"}, 3_000),
    ],
)
def test_multimodal_chat_strict_category_and_budget_filters(
    auth_client: TestClient,
    created_chat_conversations: list[int],
    query: str,
    expected_categories: set[str],
    max_price: int | None,
) -> None:
    response = auth_client.post("/api/v1/chat/message", data={"message": query})

    assert response.status_code == 200, response.text
    payload = response.json()
    created_chat_conversations.append(payload["conversation_id"])
    assert payload["products"]
    assert all(product["category"] in expected_categories for product in payload["products"])
    if max_price is not None:
        assert all(product["price"] <= max_price for product in payload["products"])


def test_marketplace_seeded_products_have_categories_and_stock() -> None:
    expected_categories = {
        "embroidered-formal-lawn-suit": "Dresses & Fashion",
        "elegant-party-wear-maxi": "Dresses & Fashion",
        "casual-cotton-kurti": "Dresses & Fashion",
        "matte-liquid-lipstick-set": "Makeup & Beauty",
        "professional-eyeshadow-palette-24": "Makeup & Beauty",
        "minimalist-wooden-coffee-table": "Furniture",
        "3d-self-adhesive-wall-stickers": "Wallpapers",
        "compact-capsule-coffee-machine": "Home Appliances",
    }
    with SessionLocal() as db:
        products = db.query(Product).filter(Product.id.in_(expected_categories)).all()

    assert {product.id: product.category for product in products} == expected_categories
    assert all(product.stock_count > 0 for product in products)


def test_multimodal_chat_requires_message_or_image(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/chat/message", data={"message": " "})

    assert response.status_code == 422

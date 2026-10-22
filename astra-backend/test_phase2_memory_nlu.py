"""Safe isolated tests for shopping NLU and user-scoped memory.

This module intentionally lives outside tests/conftest.py. It uses a private
in-memory SQLite DB and never imports app.main or shared commerce fixtures.
"""
import asyncio

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models  # Register relationship targets without bootstrapping the application.
from app.api.v1.endpoints import chat
from app.api.v1.endpoints import explore as explore_endpoint
from app.core.database import Base
from app.models.chat import ChatConversation, ChatMessage
from app.models.shopping_preference import ShoppingPreference
from app.models.user import User
from app.services.shopping_memory import get_user_shopping_preferences
from app.services.shopping_memory import negotiation_preferences
from app.services.shopping_nlu import extract_explicit_preferences, parse_shopping_intent
from app.services.explore import FusedSearchResult


def test_multilingual_constraints_and_budget_phrases() -> None:
    roman_urdu = parse_shopping_intent(
        "Mujhe red color mein medium size ki formal shirt chahiye under 3000 PKR."
    )
    english = parse_shopping_intent("I need a red medium formal shirt under 3000 PKR")
    urdu = parse_shopping_intent(
        "مجھے لال رنگ میں درمیانہ سائز کی فارمل قمیض چاہیے ۳۰۰۰ سے کم روپے"
    )

    for result in (roman_urdu, english, urdu):
        assert result.category == "Clothing & Fashion"
        assert result.color == "red"
        assert result.size == "M"
        assert result.budget_max == 3000

    assert parse_shopping_intent("3000 se kam").budget_max == 3000
    assert parse_shopping_intent("3000 tak").budget_max == 3000
    assert parse_shopping_intent("mera budget 2500 hai").budget_max == 2500
    assert parse_shopping_intent("between 1000 and 3000 PKR").budget_min == 1000
    assert parse_shopping_intent("gaming laptop under 200k").budget_max == 200000
    ambiguous = parse_shopping_intent("red or blue shirt, laptop or phone under 3000 USD")
    assert ambiguous.color is None and ambiguous.category is None and ambiguous.budget_max is None


def test_unknown_input_is_not_guessed_and_memory_requires_explicit_preference() -> None:
    unknown = parse_shopping_intent("maybe find something nice")
    assert unknown.category is unknown.color is unknown.size is None
    assert unknown.budget_min is unknown.budget_max is None
    assert extract_explicit_preferences("red shirt under 3000") == {}
    assert extract_explicit_preferences("I prefer red, medium size, cotton shirts; my budget is 2500") == {
        "clothing_size": "M", "favorite_color": "red", "budget_max": 2500.0,
        "shopping_preferences": ["cotton"],
        "preferred_category": "Clothing & Fashion",
    }
    assert negotiation_preferences({
        "clothing_size": "M", "favorite_color": "red", "budget_max": 2500,
        "shopping_preferences": ["cotton"],
    }) == {"clothing_size": "M", "favorite_color": "red", "shopping_preferences": ["cotton"]}


def test_buy_intent_remains_search_only(monkeypatch) -> None:
    from app.services import explore

    monkeypatch.setattr(explore.product_repository, "list_products", lambda: [{
        "id": "demo-laptop", "title": "Lenovo Laptop", "category": "Laptops & Computers",
        "search_terms": "lenovo laptop computer", "semantic_tags": [], "trust": 90,
        "rating": 4.5, "price": 150000, "image_url": "", "seller_name": "Demo",
        "is_verified_seller": True,
    }])
    response = explore.resolve_purchase_intent("buy lenovo laptop under 200k")
    assert response["intent"] == "buy"
    assert response["action"]["type"] == "search"
    assert response["auto_checkout"] is False


def test_voice_intent_endpoint_returns_multilingual_constraints_without_checkout(monkeypatch) -> None:
    monkeypatch.setattr(explore_endpoint, "resolve_purchase_intent", lambda query, _labels: {
        "query": query, "intent": "browse", "action": {"type": "checkout", "label": "ignored", "verb": None},
        "budget": None, "category": None, "matched_product": None, "alternatives": [],
        "auto_checkout": True, "confidence": 0.8,
    })
    response = asyncio.run(explore_endpoint.voice_intent(
        query="مجھے لال رنگ میں درمیانہ سائز کی فارمل قمیض چاہیے ۳۰۰۰ سے کم روپے",
        image_file=None,
    ))
    assert response["query"].startswith("مجھے")
    assert response["constraints"] == {
        "category": "Clothing & Fashion", "color": "red", "size": "M",
        "budget_min": None, "budget_max": 3000.0,
    }
    assert response["action"]["type"] == "search"
    assert response["auto_checkout"] is False


def test_text_search_route_applies_roman_urdu_budget_but_stays_search_only(monkeypatch) -> None:
    captured = {}

    async def fake_execute(request, _audio, _image):
        captured["request"] = request
        return FusedSearchResult(results=[], query=request.text_query or "", signals=[], image_labels=[])

    monkeypatch.setattr(explore_endpoint, "execute_search", fake_execute)
    response = asyncio.run(explore_endpoint.search(
        query_type="text", text_query="laptop 3000 se kam", category="All",
        min_price=0, max_price=500000, semantic_tags=None, sort_by="most_relevant",
        page=1, limit=10, audio_file=None, image_file=None,
    ))
    assert captured["request"].max_price == 3000
    assert response.query == "laptop 3000 se kam"
    assert response.total_results == 0
    assert not hasattr(response, "checkout_ref")


def _memory_db() -> tuple[object, User, User]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[
        User.__table__, ShoppingPreference.__table__, ChatConversation.__table__, ChatMessage.__table__,
    ])
    with Session(engine) as db:
        first = User(name="Buyer One", email="one@example.test", hashed_password="not-a-real-hash")
        second = User(name="Buyer Two", email="two@example.test", hashed_password="not-a-real-hash")
        db.add_all([first, second])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        return engine, first, second


def test_preferences_persist_across_conversations_and_are_user_isolated(monkeypatch) -> None:
    engine, first_user, second_user = _memory_db()
    # The endpoint only needs these columns for its honesty check; no catalogue
    # rows are seeded or modified by this isolated test.
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE products (id TEXT PRIMARY KEY, listing_status TEXT, color TEXT, size TEXT)"
        ))
    captured: list[dict] = []
    monkeypatch.setattr(chat, "_matching_products", lambda _db, _query, preferences=None: captured.append(preferences or {}) or [])

    with Session(engine) as db:
        first_response = asyncio.run(chat.send_multimodal_message(
            message="I prefer red, medium size, cotton shirts; my budget is 2500",
            conversation_id=None, image=None, db=db, current_user=first_user,
        ))
        first_conversation_id = first_response["conversation_id"]
        assert first_response["detected_constraints"]["color"] == "red"
        assert first_response["detected_constraints"]["size"] == "M"
        assert "checkout_ref" not in first_response and "consent_id" not in first_response

    # A later turn and a new conversation for the same account receive memory.
    with Session(engine) as db:
        asyncio.run(chat.send_multimodal_message(
            message="show me a formal shirt", conversation_id=first_conversation_id,
            image=None, db=db, current_user=first_user,
        ))
        assert captured[-1]["favorite_color"] == "red"
        asyncio.run(chat.send_multimodal_message(
            message="show me a formal shirt", conversation_id=None,
            image=None, db=db, current_user=first_user,
        ))
        preferences = get_user_shopping_preferences(db, first_user.id)
        assert preferences["clothing_size"] == "M"
        assert preferences["favorite_color"] == "red"
        assert preferences["budget_max"] == 2500
        assert preferences["shopping_preferences"] == ["cotton"]
        stored = db.get(ShoppingPreference, first_user.id)
        assert stored is not None
        assert "I prefer" not in stored.shopping_preferences_json
        assert captured[-1]["favorite_color"] == "red"

        with pytest.raises(HTTPException) as error:
            asyncio.run(chat.send_multimodal_message(
                message="continue", conversation_id=first_conversation_id,
                image=None, db=db, current_user=second_user,
            ))
        assert error.value.status_code == 404

    with Session(engine) as db:
        assert get_user_shopping_preferences(db, second_user.id) == {}
        asyncio.run(chat.send_multimodal_message(
            message="find a shirt", conversation_id=None, image=None,
            db=db, current_user=second_user,
        ))
        assert captured[-1] == {}
        assert db.get(ShoppingPreference, second_user.id) is None

    engine.dispose()


def test_preference_update_replaces_stale_budget_range() -> None:
    from app.services.shopping_memory import remember_explicit_preferences

    engine, first_user, _ = _memory_db()
    with Session(engine) as db:
        remember_explicit_preferences(db, first_user.id, "My budget range is 2000 to 4000 PKR")
        updated = remember_explicit_preferences(db, first_user.id, "My budget is 2500 PKR")
        assert updated["budget_min"] is None
        assert updated["budget_max"] == 2500
    engine.dispose()


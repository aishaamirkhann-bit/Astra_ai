"""Persistence and safe projection of explicitly shared shopping preferences."""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.shopping_preference import ShoppingPreference
from app.services.shopping_nlu import extract_explicit_preferences


def get_user_shopping_preferences(db: Session, user_id: int) -> dict[str, Any]:
    """Load only the authenticated user's small preference record."""
    record = db.get(ShoppingPreference, user_id)
    if record is None:
        return {}
    try:
        preferences = json.loads(record.shopping_preferences_json or "[]")
    except (TypeError, json.JSONDecodeError):
        preferences = []
    if not isinstance(preferences, list):
        preferences = []
    return {
        "clothing_size": record.clothing_size,
        "favorite_color": record.favorite_color,
        "preferred_category": record.preferred_category,
        "budget_min": record.budget_min,
        "budget_max": record.budget_max,
        "shopping_preferences": [item for item in preferences if isinstance(item, str)][:20],
    }


def remember_explicit_preferences(db: Session, user_id: int, message: str) -> dict[str, Any]:
    """Upsert normalized whitelisted facets, never the raw user message."""
    extracted = extract_explicit_preferences(message)
    record = db.get(ShoppingPreference, user_id)
    if not extracted:
        return get_user_shopping_preferences(db, user_id)
    if record is None:
        record = ShoppingPreference(user_id=user_id, shopping_preferences_json="[]")
        db.add(record)
    if "budget_min" in extracted or "budget_max" in extracted:
        record.budget_min = extracted.get("budget_min")
        record.budget_max = extracted.get("budget_max")
    for field in ("clothing_size", "favorite_color", "budget_min", "budget_max", "preferred_category"):
        if field in extracted and field not in {"budget_min", "budget_max"}:
            setattr(record, field, extracted[field])
    if "shopping_preferences" in extracted:
        try:
            existing = json.loads(record.shopping_preferences_json or "[]")
        except (TypeError, json.JSONDecodeError):
            existing = []
        if not isinstance(existing, list):
            existing = []
        record.shopping_preferences_json = json.dumps(
            list(dict.fromkeys([item for item in existing if isinstance(item, str)] + extracted["shopping_preferences"]))[:20]
        )
    db.flush()
    return get_user_shopping_preferences(db, user_id)


def preference_context(preferences: dict[str, Any]) -> str:
    """Human-readable advisory summary; omits empty and financial-account data."""
    parts = []
    if preferences.get("clothing_size"):
        parts.append(f"usual clothing size {preferences['clothing_size']}")
    if preferences.get("favorite_color"):
        parts.append(f"favorite color {preferences['favorite_color']}")
    if preferences.get("budget_min") is not None or preferences.get("budget_max") is not None:
        low = preferences.get("budget_min")
        high = preferences.get("budget_max")
        if low is not None and high is not None:
            parts.append(f"shopping budget range Rs. {low:,.0f}–{high:,.0f}")
        elif high is not None:
            parts.append(f"stated shopping budget up to Rs. {high:,.0f}")
        else:
            parts.append(f"stated shopping budget from Rs. {low:,.0f}")
    if preferences.get("preferred_category"):
        parts.append(f"preferred category {preferences['preferred_category']}")
    for preference in preferences.get("shopping_preferences", []):
        if preference not in parts:
            parts.append(str(preference))
    return "; ".join(parts)


def negotiation_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    """Non-financial preference facets suitable as advisory negotiation context."""
    return {
        key: preferences[key]
        for key in ("clothing_size", "favorite_color", "preferred_category", "shopping_preferences")
        if preferences.get(key)
    }

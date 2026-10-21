from copy import deepcopy
from types import SimpleNamespace

from app.core.database import SessionLocal
from app.models.product import Product
from app.models.wallet import UserWallet
from app.services.outfit_stylist import build_outfit_recommendations


def item(id, title, category, color="", price=1000, stock=5, tags=""):
    return SimpleNamespace(id=id, title=title, category=category, subcategory="",
                           search_terms=tags, semantic_tags="", quality_tags="",
                           description="", color=color, base_price=price,
                           image_url=f"/{id}.jpg", stock_count=stock,
                           listing_status="active", rating=4.5)


def test_kurta_outfit_matches_bottom_shoes_and_accessories():
    kurta = item("kurta", "Black embroidered kurta", "Dresses & Fashion", "black", tags="festive formal")
    catalog = [
        item("pants", "Gold formal trousers", "Fashion", "gold", tags="formal bottomwear"),
        item("shoes", "Black formal shoes", "Footwear", "black", tags="formal"),
        item("dupatta", "Gold dupatta", "Accessories", "gold", tags="formal"),
        item("other-kurta", "Black kurta", "Fashion", "black"),
    ]
    result = build_outfit_recommendations(kurta, catalog)
    slots = {entry["slot"] for entry in result["outfits"][0]["items"]}
    assert slots == {"main", "bottom", "shoes", "accessory"}
    assert result["outfits"][0]["estimated_total"] == 4000
    assert any("Formal style match" in reason for entry in result["outfits"][0]["items"] for reason in entry["reasons"])


def test_shoes_anchor_recommends_clothing_categories():
    shoes = item("shoes", "Brown leather shoes", "Footwear", "brown")
    result = build_outfit_recommendations(shoes, [
        item("shirt", "White formal shirt", "Fashion", "white", tags="formal"),
        item("pants", "Navy formal pants", "Fashion", "navy", tags="formal"),
    ])
    assert {entry["slot"] for entry in result["outfits"][0]["items"]} == {"main", "top", "bottom"}


def test_no_complementary_inventory_returns_clear_fallback():
    result = build_outfit_recommendations(item("shirt", "Cotton shirt", "Fashion"), [])
    assert result["outfits"] == []
    assert "No complementary" in result["message"]


def test_recommendation_logic_does_not_mutate_catalogue_objects():
    anchor = item("kurta", "Red kurta", "Fashion", "red")
    candidates = [item("pants", "Black pants", "Fashion", "black")]
    before = deepcopy((vars(anchor), [vars(candidate) for candidate in candidates]))
    recommendation = build_outfit_recommendations(anchor, candidates)
    assert recommendation["outfits"]
    assert (vars(anchor), [vars(candidate) for candidate in candidates]) == before


def test_recommendation_endpoint_leaves_catalogue_and_wallet_unchanged(auth_client, demo_user_id):
    with SessionLocal() as db:
        product = db.query(Product).filter(Product.listing_status == "active").first()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).first()
        assert product and wallet
        product_id = product.id
        stock_before = product.stock_count
        balance_before = wallet.available_balance
        product_count_before = db.query(Product).count()

    response = auth_client.get(f"/api/v1/products/{product_id}/outfit-recommendations")
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.query(Product).count() == product_count_before
        assert db.get(Product, product_id).stock_count == stock_before
        assert db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one().available_balance == balance_before

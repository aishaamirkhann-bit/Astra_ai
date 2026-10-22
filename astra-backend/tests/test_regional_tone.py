from app.core.database import SessionLocal
from app.models.order import Order
from app.models.product import Product
from app.models.wallet import UserWallet
from app.services.buyer_tone import sense_buyer_tone
from app.services.shopping_nlu import parse_regional_intent


def test_punjabi_phrase_maps_to_clothing_style_and_negotiation():
    result = parse_regional_intent("Sohnra suit black shaadi wala, rate ghat karo")

    assert result["dialect"] == "Punjabi"
    assert result["category"] == "Clothing & Fashion"
    assert result["color"] == "black"
    assert result["style"] == "wedding"
    assert result["negotiation_requested"] is True
    assert result["advisory_only"] is True


def test_pashto_phrase_maps_to_clothing_color_and_price_request():
    result = parse_regional_intent("Khaista jora tor rang, qeemat kam")

    assert result["dialect"] == "Pashto"
    assert result["category"] == "Clothing & Fashion"
    assert result["color"] == "black"
    assert result["negotiation_requested"] is True


def test_sindhi_phrase_maps_to_clothing_color_and_negotiation():
    result = parse_regional_intent("Sutho dress surkho, bhaao ghataayo")

    assert result["dialect"] == "Sindhi"
    assert result["category"] == "Clothing & Fashion"
    assert result["color"] == "red"
    assert result["negotiation_requested"] is True


def test_buyer_tone_returns_advisory_prompt_for_explicit_cues():
    price = sense_buyer_tone("Bohot mehnga hai")
    hesitant = sense_buyer_tone("I am confused about size")
    intent = sense_buyer_tone("Abhi khareedna hai")

    assert price.category == "price_sensitive"
    assert "price floor" in price.assistance_prompt
    assert hesitant.category == "hesitant"
    assert "size guide" in hesitant.assistance_prompt
    assert intent.category == "high_intent"
    assert "explicit tasdeeq" in intent.assistance_prompt
    assert all(item.as_dict()["advisory_only"] for item in (price, hesitant, intent))


def test_tone_analysis_does_not_change_catalogue_orders_or_wallet(demo_user_id):
    with SessionLocal() as db:
        product_state = [
            (row.id, row.base_price, row.stock_count, row.listing_status)
            for row in db.query(Product).order_by(Product.id).all()
        ]
        order_state = [
            (row.id, row.status.value, row.price)
            for row in db.query(Order).order_by(Order.id).all()
        ]
        wallet_state = tuple(
            db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one().__getattribute__(field)
            for field in ("available_balance", "frozen_balance")
        )

    result = sense_buyer_tone("Bohot mehnga hai; koi sasta option hai?")
    assert result.category == "price_sensitive"

    with SessionLocal() as db:
        assert [
            (row.id, row.base_price, row.stock_count, row.listing_status)
            for row in db.query(Product).order_by(Product.id).all()
        ] == product_state
        assert [
            (row.id, row.status.value, row.price)
            for row in db.query(Order).order_by(Order.id).all()
        ] == order_state
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one()
        assert (wallet.available_balance, wallet.frozen_balance) == wallet_state

import json
import re
import asyncio
import inspect
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.chat import ChatConversation, ChatMessage
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.order_return import OrderReturnRequest
from app.models.user import User
from app.services.shopping_memory import get_user_shopping_preferences, preference_context, remember_explicit_preferences
from app.services.order_operations import calculate_bundle_offer, parse_bundle_request, parse_order_operation, return_eligibility
from app.services.shopping_nlu import detect_greeting, greeting_response, normalize_shopping_text, parse_shopping_intent, product_matches_response
from app.services.shopping_nlu import parse_regional_intent
from app.services.buyer_tone import sense_buyer_tone
from app.services.vision import describe_image_for_chat
from app.services.localization import cross_border_advisory, detect_locale, localized, mirror_language_text
from app.services.outfit_stylist import build_outfit_recommendations

router = APIRouter(prefix="/chat", tags=["AI Chat"])
MAX_CHAT_IMAGE_BYTES = 8 * 1024 * 1024
SUPPORTED_CHAT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
CHAT_QUERY_STOP_WORDS = {
    "a", "about", "an", "and", "andar", "are", "batao", "can", "chahiye",
    "could", "dekhao", "dikhao", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "ke", "karo", "mein", "me", "mujhe", "my", "of",
    "on", "or", "please", "recommend", "show", "some", "tak", "tell",
    "than", "that", "the", "this", "to", "under", "what", "which", "with",
    "would", "you", "your", "ho", "hain", "room", "rooms", "neutral",
    "wall", "walls", "open", "floor", "space", "visible", "image",
}
CATEGORY_INTENTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("laptop bag", "laptop backpack"), ("Electronics & Accessories", "Accessories")),
    (("dresses", "dress", "fashion", "clothes", "clothing", "kapray", "kurti", "kurtis", "maxi", "hoodie", "lawn suit", "bag"), ("Dresses & Fashion", "Clothing & Fashion")),
    (("makeup", "make up", "beauty", "lipstick", "eyeshadow", "serum", "cosmetics", "skincare"), ("Makeup & Beauty",)),
    (("wallpaper", "wallpapers", "wall sticker", "wall stickers"), ("Wallpapers",)),
    (("furniture", "chair", "coffee table", "sofa", "desk"), ("Furniture",)),
    (("tapestry", "tapestries"), ("Home & Living",)),
    (("home decor", "home decoration", "room decor", "decoration", "decor", "tapestry"), ("Furniture", "Wallpapers", "Home & Living")),
    (("air fryer", "coffee machine", "kitchen appliance", "home appliance", "appliances"), ("Home Appliances",)),
    (("laptops", "laptop", "notebook", "computer", "macbook"), ("Laptops & Computers",)),
    (("phones", "phone", "mobiles", "mobile", "smartphone", "iphone"), ("Mobiles",)),
    (("headphones", "headphone", "earbuds", "earbud", "speaker", "audio"), ("Audio & Wearables",)),
    (("smartwatch", "wearable", "watch"), ("Wearables", "Audio & Wearables")),
    (("power bank", "charger", "charging", "ssd", "camera"), ("Electronics & Accessories", "Accessories")),
    (("electronics", "electronic"), ("Electronics & Accessories", "Accessories", "Mobiles", "Laptops & Computers", "Audio & Wearables", "Wearables")),
    (("accessories", "accessory"), ("Electronics & Accessories", "Accessories")),
    (("jewelry", "jewellery", "earrings", "necklace", "bracelet", "ring"), ("Jewelry",)),
)
_AMOUNT = r"(?:rs\.?\s*)?(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>thousand|lakh|lac|k)?(?![a-z])"
_BUDGET_PREFIX = re.compile(
    rf"(?:under|below|less than|ke under|ke andar|andar|tak|maximum|max|within|up to|upto|budget(?:\s+(?:of|is))?|mein)\s*{_AMOUNT}"
)
_BUDGET_SUFFIX = re.compile(
    rf"(?:jo\s+)?{_AMOUNT}\s*(?:ke\s+)?(?:under|below|andar|tak|mein)(?:\s+ho)?\b"
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


def _product_card(product: Product, destination: str, locale: str) -> dict:
    return {"slug": product.slug, "name": product.name, "category": product.category, "price": product.price,
            "image": product.image_url, "seller": product.seller_name, "trust": product.trust_score,
            "stock": product.stock_count, "origin_country": product.origin_country,
            "cross_border_advisory": cross_border_advisory(product.origin_country or "PK", destination,
                                                             float(product.price), locale)}


def _deduplicate_products(products: list[Product]) -> list[Product]:
    """Drop repeated catalog rows while preserving separate color variants."""
    seen: set[tuple] = set()
    unique = []
    for product in products:
        key = (re.sub(r"\W+", " ", (product.title or "").lower()).strip(),
               round(float(product.price or 0), 2), (product.color or "").strip().lower(),
               (product.size or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(product)
    return unique


def _chat_locale(text: str, preferred_language: str | None) -> str:
    normalized = text.strip().lower()
    if re.fullmatch(r"(?:hello|hi)[!.?, ]*", normalized): return "en"
    if re.fullmatch(r"(?:salaam|salam|assalam o alaikum|assalamu alaikum|as-salamu alaykum)[!.?, ]*", normalized): return "roman_urdu"
    if "??" in text: return "zh"
    if "????" in text: return "fa"
    detected = detect_locale(text)
    preferred = detect_locale("", preferred_language)
    # Salutations such as "salaam" are commonly used across languages. Use the
    # user's saved locale when available, while still recognizing script-based
    # greetings and the explicitly Roman Urdu fallback.
    if detect_greeting(text) and detected in {"en", "roman_urdu"} and preferred != "en":
        return preferred
    return detected if detected != "en" else preferred


def _parse_budget(query: str) -> float | None:
    intent = parse_shopping_intent(query)
    if intent.budget_max is not None:
        return intent.budget_max
    normalized = query.lower().replace(",", "")
    match = _BUDGET_PREFIX.search(normalized) or _BUDGET_SUFFIX.search(normalized)
    if match is None:
        return None
    amount = float(match.group("amount"))
    multiplier = match.group("unit")
    if multiplier in {"k", "thousand"}:
        amount *= 1_000
    elif multiplier in {"lac", "lakh"}:
        amount *= 100_000
    return amount


def _category_filter(query: str) -> tuple[str, ...]:
    intent = parse_shopping_intent(query)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalize_shopping_text(query)).strip()
    for aliases, categories in CATEGORY_INTENTS:
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            for alias in aliases
        ):
            return categories
    if intent.category == "Clothing & Fashion":
        return ("Dresses & Fashion", "Clothing & Fashion")
    if intent.category:
        return (intent.category,)
    return ()


def _matching_products(db: Session, query: str, preferences: dict | None = None) -> list[Product]:
    normalized = normalize_shopping_text(query).replace(",", "")
    budget = _parse_budget(query)
    categories = _category_filter(normalized)
    intent = parse_shopping_intent(query)
    query_terms = {
        term for term in re.findall(r"[a-z0-9]+", normalized)
        if len(term) > 2 and term not in CHAT_QUERY_STOP_WORDS
    }
    if not query_terms and not categories:
        return []

    products_query = db.query(Product).filter(
        Product.listing_status == "active",
        Product.stock_count > 0,
    )
    if categories:
        products_query = products_query.filter(Product.category.in_(categories))
    if budget is not None:
        products_query = products_query.filter(Product.price <= budget)
    color_supported = bool(intent.color and db.query(Product.id).filter(
        Product.listing_status == "active", Product.color.is_not(None), Product.color != "",
    ).first())
    size_supported = bool(intent.size and db.query(Product.id).filter(
        Product.listing_status == "active", Product.size.is_not(None), Product.size != "",
    ).first())
    if intent.color and color_supported:
        products_query = products_query.filter(Product.color.ilike(f"%{intent.color}%"))
    if intent.size and size_supported:
        products_query = products_query.filter(Product.size.ilike(f"%{intent.size}%"))

    ranked: list[tuple[int, Product]] = []
    for product in products_query.all():
        searchable = f"{product.title} {product.category} {product.search_terms}".lower()
        score = sum(term in searchable for term in query_terms)
        if preferences:
            preferred_category = preferences.get("preferred_category")
            clothing_category_match = preferred_category == "Clothing & Fashion" and product.category == "Dresses & Fashion"
            if preferred_category == product.category or clothing_category_match:
                score += 1
            if preferences.get("favorite_color") and preferences["favorite_color"] in (product.color or "").lower():
                score += 1
            if preferences.get("clothing_size") and preferences["clothing_size"].lower() in (product.size or "").lower():
                score += 1
            if preferences.get("budget_max") is not None and product.price <= preferences["budget_max"]:
                score += 1
            score += sum(term in searchable for term in preferences.get("shopping_preferences", []))
        if score or categories:
            ranked.append((score, product))
    ranked.sort(key=lambda item: (item[0], item[1].trust_score, item[1].rating), reverse=True)
    return _deduplicate_products([product for _, product in ranked])[:3]


@router.get("/history")
def history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversations = db.query(ChatConversation).filter(ChatConversation.user_id == current_user.id).order_by(ChatConversation.created_at.desc()).all()
    return [{"id": conversation.id, "title": conversation.title, "messages": [{"id": message.id, "role": message.role, "content": message.content, "card_type": message.card_type, "card": json.loads(message.card_payload) if message.card_payload else None, "created_at": message.created_at} for message in conversation.messages]} for conversation in conversations]


@router.post("/message")
async def send_multimodal_message(
    message: str = Form(default="", max_length=2000),
    conversation_id: int | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Send a text question with an optional gallery/camera image."""
    text = message.strip()
    locale = _chat_locale(text, current_user.preferred_language)
    if not text and image is None:
        raise HTTPException(status_code=422, detail="Enter a message or attach an image.")
    if image is not None and image.content_type not in SUPPORTED_CHAT_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WebP image.")

    conversation = (
        db.query(ChatConversation)
        .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == current_user.id)
        .first()
        if conversation_id
        else None
    )
    if conversation_id and conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation is None:
        conversation = ChatConversation(user_id=current_user.id, title=(text or "Image question")[:70])
        db.add(conversation)
        db.flush()

    # Existing conversations and new sessions both begin with preferences
    # scoped to the authenticated account. Store only explicit normalized facets.
    preferences = get_user_shopping_preferences(db, current_user.id)
    if text:
        preferences = remember_explicit_preferences(db, current_user.id, text)

    image_bytes = b""
    image_result = None
    if image is not None:
        image_bytes = await image.read(MAX_CHAT_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_CHAT_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
        if not image_bytes:
            raise HTTPException(status_code=422, detail="The selected image is empty.")
        image_args = (image_bytes, image.content_type or "image/jpeg", text)
        supports_locale = len(inspect.signature(describe_image_for_chat).parameters) >= 4
        image_result = await asyncio.to_thread(describe_image_for_chat, *image_args, locale) if supports_locale else await asyncio.to_thread(describe_image_for_chat, *image_args)

    user_content = text or "Please describe this image."
    user_message = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=user_content,
        card_type="image_attachment" if image is not None else None,
        card_payload=json.dumps({"filename": image.filename}) if image is not None else None,
    )
    db.add(user_message)

    query = text
    image_answer = image_result.answer if image_result and image_result.status == "analyzed" else None
    response_card = None
    response_card_type = None
    order_operation = parse_order_operation(text)
    bundle_request = parse_bundle_request(text)
    if image_answer:
        query = f"{text} {image_answer}".strip()
        reply = image_answer
    elif detect_greeting(text):
        reply = greeting_response(locale)
    elif image is not None:
        if image_result and image_result.status == "provider_error":
            reply = (
                "I received your image, but ASTRA Vision couldn't analyze it right now. "
                "Please try again in a moment or describe the image in your message. "
                "I can still help with product searches from your text."
            )
        else:
            reply = (
                "I received your image, but image understanding is not configured yet. "
                "Set VISION_PROVIDER=groq and VISION_API_KEY in the backend environment, "
                "then restart the API. I can still help with product searches from your text."
            )
    elif bundle_request:
        lines = []
        for requested in bundle_request:
            hint = requested["product_hint"]
            quantity = int(requested["quantity"])
            conditions = {
                "shirt": (Product.title.ilike("%shirt%"), Product.category.ilike("%cloth%"), Product.category.ilike("%dress%")),
                "shoes": (Product.title.ilike("%shoe%"), Product.category.ilike("%footwear%")),
                "laptop": (Product.title.ilike("%laptop%"), Product.category.ilike("%computer%")),
                "phone": (Product.title.ilike("%phone%"), Product.category.ilike("%mobile%")),
            }[hint]
            product = db.query(Product).filter(
                Product.listing_status == "active", Product.stock_count >= quantity,
                or_(*conditions),
            ).order_by(Product.trust.desc(), Product.rating.desc(), Product.base_price.asc()).first()
            if product:
                lines.append({
                    "product_id": product.id, "title": product.title,
                    "quantity": quantity, "price": product.base_price,
                    "seller_price_floor": product.seller_price_floor or product.base_price,
                })
        if len(lines) != len(bundle_request):
            reply = "I couldn't match every item in that bundle to an in-stock catalog listing. Please choose each product from the catalog first."
        else:
            quote = calculate_bundle_offer(lines)
            response_card_type = "bundle_advisory"
            response_card = quote
            reply = "Here is a non-binding bundle estimate using the selected in-stock listings and their seller price floors. Review the details below; this does not place an order."
    elif order_operation.action in {"track", "return_request", "exchange_request"}:
        order_query = db.query(Order).filter(Order.user_id == current_user.id)
        if order_operation.product_hint:
            order_query = order_query.join(Order.product).filter(
                Product.title.ilike(f"%{order_operation.product_hint}%")
                if order_operation.product_hint not in {"shirt", "shoes"}
                else (Product.title.ilike("%shirt%") | Product.title.ilike("%shoe%") | Product.category.ilike("%cloth%") | Product.category.ilike("%footwear%"))
            )
        orders = order_query.order_by(Order.created_at.desc()).limit(10).all()
        if not orders:
            reply = "I couldn't find a matching order on your account. Try an order reference or open Orders & Receipts."
        elif order_operation.action == "track":
            order = orders[0]
            stages = [
                {"label": "Processing", "status": "done" if order.status != OrderStatus.CANCELLED else "cancelled"},
                {"label": "Shipped", "status": "done" if order.status in {OrderStatus.SHIPPED, OrderStatus.DELIVERED} else "pending"},
                {"label": "Out for Delivery", "status": "done" if order.status == OrderStatus.DELIVERED else "pending"},
                {"label": "Delivered", "status": "done" if order.status == OrderStatus.DELIVERED else "pending"},
            ]
            response_card_type = "order_tracking"
            response_card = {"order_ref": order.order_ref, "product_name": order.product.title, "status": order.status.value, "timeline": stages}
            reply = localized(locale, "track", product=order.product.title, order_ref=order.order_ref,
                              status=order.status.value.replace("_", " "))
        else:
            order = next((candidate for candidate in orders if return_eligibility(candidate.status.value, candidate.delivered_at)[0]), orders[0])
            eligible, explanation = return_eligibility(order.status.value, order.delivered_at)
            existing = db.query(OrderReturnRequest).filter(
                OrderReturnRequest.order_id == order.id,
                OrderReturnRequest.user_id == current_user.id,
                OrderReturnRequest.status == "pending_review",
            ).first()
            response_card_type = "return_confirmation"
            response_card = {
                "order_ref": order.order_ref,
                "product_name": order.product.title,
                "request_type": order_operation.request_type or "return",
                "eligible": eligible and existing is None,
                "status": "pending_review" if existing else order.status.value,
                "explanation": "A return request is already awaiting review." if existing else explanation,
                "reason": f"Buyer requested {order_operation.request_type or 'return'} for {order.product.title}",
            }
            request_type = order_operation.request_type or "return"
            reply = (
                localized(locale, "return_confirm", request_type=request_type)
                if eligible and existing is None
                else response_card["explanation"]
            )
    elif "wallet" in text.lower():
        reply = (
            f"Your available wallet balance is Rs. {current_user.wallet.available_balance:,.0f}. "
            "Open Wallet & Ledger for the full transaction history."
        )
    else:
        reply = ""

    outfit_request = bool(re.search(r"\b(match(?:ing)?|style|styling|outfit|go(?:es)?\s+with|pair\s+with)\b", text.lower()))
    products = _matching_products(db, query, preferences) if order_operation.action is None and not bundle_request and "wallet" not in text.lower() else []
    products = _deduplicate_products(products)
    if outfit_request and products:
        anchor = products[0]
        candidates = db.query(Product).filter(Product.listing_status == "active", Product.stock_count > 0).all()
        outfit = build_outfit_recommendations(anchor, candidates, locale, current_user.country or "PK")
        if outfit.get("outfits"):
            response_card_type = "outfit_recommendations"
            response_card = outfit
            products = []
            reply = outfit["message"]
    if not reply:
        if products:
            reply = product_matches_response(locale)
            if preference_context(preferences):
                reply += f" Your saved shopping preferences are advisory: {preference_context(preferences)}."
        else:
            reply = "Tell me a little more—such as the product type, category, or your budget—and I’ll find relevant options."
    elif products and text:
        reply = f"{reply}\n\nI also found some catalog options that may fit:"

    cards = [_product_card(product, current_user.country or "PK", locale) for product in products]
    advisory_attached = False
    for card in cards:
        if card.get("cross_border_advisory"):
            if advisory_attached:
                card["cross_border_advisory"] = None
            else:
                advisory_attached = True
    border_messages = list(dict.fromkeys(card["cross_border_advisory"]["message"] for card in cards if card.get("cross_border_advisory")))
    if border_messages:
        reply += "\n\n" + border_messages[0]
    detected_constraints = parse_shopping_intent(query)
    unsupported_constraints = []
    if detected_constraints.color and not db.query(Product.id).filter(
        Product.listing_status == "active", Product.color.is_not(None), Product.color != "",
    ).first():
        unsupported_constraints.append("color")
    if detected_constraints.size and not db.query(Product.id).filter(
        Product.listing_status == "active", Product.size.is_not(None), Product.size != "",
    ).first():
        unsupported_constraints.append("size")
    if unsupported_constraints:
        reply += f" The current catalog does not record {', '.join(unsupported_constraints)} options, so those details could not be verified."
    regional_intent = parse_regional_intent(query or text)
    buyer_tone = sense_buyer_tone(query or text, locale)
    if buyer_tone.assistance_prompt:
        reply += f"\n\n{buyer_tone.assistance_prompt}"
    # Mirror the active user's language after all deterministic safety and
    # commerce wording has been assembled, including catalog/customs notices.
    if not detect_greeting(text):
        reply = await asyncio.to_thread(mirror_language_text, reply, locale)
    assistant = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
        card_type=response_card_type or ("products" if cards else None),
        card_payload=json.dumps(response_card if response_card is not None else cards) if (response_card is not None or cards) else None,
    )
    db.add(assistant)
    db.commit()
    db.refresh(assistant)
    return {
        "conversation_id": conversation.id,
        "reply_text": reply,
        "products": cards,
        "card_type": assistant.card_type,
        "card": response_card if response_card is not None else (cards or None),
        "vision_status": image_result.status if image_result else "not_requested",
        "detected_constraints": detected_constraints.public_constraints(),
        "unverified_constraints": unsupported_constraints,
        "regional_intent": regional_intent,
        "buyer_tone": buyer_tone.as_dict(),
    }


@router.post("/stream")
def stream_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.query(ChatConversation).filter(ChatConversation.id == payload.conversation_id, ChatConversation.user_id == current_user.id).first() if payload.conversation_id else None
    if payload.conversation_id and not conversation: raise HTTPException(status_code=404, detail="Conversation not found")
    if not conversation:
        conversation = ChatConversation(user_id=current_user.id, title=payload.message[:70]); db.add(conversation); db.flush()
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=payload.message))
    nlu_text = normalize_shopping_text(payload.message)
    terms = [term for term in nlu_text.replace("?", "").split() if len(term) > 2]
    products = db.query(Product).all()
    product = next((item for item in products if any(term in f"{item.title} {item.category} {item.search_terms}".lower() for term in terms)), None)
    locale = _chat_locale(payload.message, current_user.preferred_language)
    order_intent = parse_order_operation(payload.message)
    if order_intent.action == "track":
        order = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).first()
        answer = localized(locale, "track", product=order.product.title, order_ref=order.order_ref,
                           status=order.status.value.replace("_", " ")) if order else localized(locale, "wa_empty")
        product = None
    elif "wallet" in nlu_text.lower():
        answer = f"Your available wallet balance is Rs. {current_user.wallet.available_balance:,.0f}. Open Wallet & Ledger for the full transaction history."
    elif product:
        answer = f"I found {product.title} at Rs. {product.price:,.0f}. Its ASTRA trust score is {product.trust_score}/100 and live stock is {product.stock_count}."
    else:
        answer = "I can help search products, compare verified deals, inspect trust, check your wallet, or prepare a budget-safe cart."
    card = _product_card(product, current_user.country or "PK", locale) if product else None
    if card and card.get("cross_border_advisory"):
        answer += " " + card["cross_border_advisory"]["message"]
    assistant = ChatMessage(conversation_id=conversation.id, role="assistant", content=answer, card_type="product" if card else None, card_payload=json.dumps(card) if card else None)
    db.add(assistant); db.commit(); db.refresh(assistant)
    conversation_id = conversation.id
    assistant_id = assistant.id

    def tokens() -> Iterator[str]:
        yield json.dumps({"type": "meta", "conversation_id": conversation_id, "message_id": assistant_id}) + "\n"
        for token in answer.split(" "):
            yield json.dumps({"type": "token", "value": token + " "}) + "\n"
        if card: yield json.dumps({"type": "card", "card_type": "product", "payload": card}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(tokens(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    if not audio.content_type or not audio.content_type.startswith("audio/"): raise HTTPException(status_code=415, detail="An audio recording is required")
    await audio.read()
    return {"transcript": "", "language": current_user.preferred_language, "provider": "browser-fallback", "message": "Configure STT_PROVIDER for server transcription"}

import json
import re
import asyncio
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.chat import ChatConversation, ChatMessage
from app.models.product import Product
from app.models.user import User
from app.services.vision import describe_image_for_chat

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


def _product_card(product: Product) -> dict:
    return {"slug": product.slug, "name": product.name, "category": product.category, "price": product.price, "image": product.image_url, "seller": product.seller_name, "trust": product.trust_score, "stock": product.stock_count}


def _parse_budget(query: str) -> float | None:
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
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    for aliases, categories in CATEGORY_INTENTS:
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            for alias in aliases
        ):
            return categories
    return ()


def _matching_products(db: Session, query: str) -> list[Product]:
    normalized = query.lower().replace(",", "")
    budget = _parse_budget(query)
    categories = _category_filter(query)
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

    ranked: list[tuple[int, Product]] = []
    for product in products_query.all():
        searchable = f"{product.title} {product.category} {product.search_terms}".lower()
        score = sum(term in searchable for term in query_terms)
        if score or categories:
            ranked.append((score, product))
    ranked.sort(key=lambda item: (item[0], item[1].trust_score, item[1].rating), reverse=True)
    return [product for _, product in ranked[:3]]


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

    image_bytes = b""
    image_result = None
    if image is not None:
        image_bytes = await image.read(MAX_CHAT_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_CHAT_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
        if not image_bytes:
            raise HTTPException(status_code=422, detail="The selected image is empty.")
        image_result = await asyncio.to_thread(
            describe_image_for_chat,
            image_bytes,
            image.content_type or "image/jpeg",
            text,
        )

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
    if image_answer:
        query = f"{text} {image_answer}".strip()
        reply = image_answer
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
    elif "wallet" in text.lower():
        reply = (
            f"Your available wallet balance is Rs. {current_user.wallet.available_balance:,.0f}. "
            "Open Wallet & Ledger for the full transaction history."
        )
    else:
        reply = ""

    products = _matching_products(db, query) if "wallet" not in text.lower() else []
    if not reply:
        if products:
            reply = "Here are a few matching products from the catalog."
        else:
            reply = "Tell me a little more—such as the product type, category, or your budget—and I’ll find relevant options."
    elif products and text:
        reply = f"{reply}\n\nI also found some catalog options that may fit:"

    cards = [_product_card(product) for product in products]
    assistant = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
        card_type="products" if cards else None,
        card_payload=json.dumps(cards) if cards else None,
    )
    db.add(assistant)
    db.commit()
    db.refresh(assistant)
    return {
        "conversation_id": conversation.id,
        "reply_text": reply,
        "products": cards,
        "vision_status": image_result.status if image_result else "not_requested",
    }


@router.post("/stream")
def stream_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.query(ChatConversation).filter(ChatConversation.id == payload.conversation_id, ChatConversation.user_id == current_user.id).first() if payload.conversation_id else None
    if payload.conversation_id and not conversation: raise HTTPException(status_code=404, detail="Conversation not found")
    if not conversation:
        conversation = ChatConversation(user_id=current_user.id, title=payload.message[:70]); db.add(conversation); db.flush()
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=payload.message))
    terms = [term for term in payload.message.lower().replace("?", "").split() if len(term) > 2]
    products = db.query(Product).all()
    product = next((item for item in products if any(term in f"{item.title} {item.category} {item.search_terms}".lower() for term in terms)), None)
    if "wallet" in payload.message.lower():
        answer = f"Your available wallet balance is Rs. {current_user.wallet.available_balance:,.0f}. Open Wallet & Ledger for the full transaction history."
    elif product:
        answer = f"I found {product.title} at Rs. {product.price:,.0f}. Its ASTRA trust score is {product.trust_score}/100 and live stock is {product.stock_count}."
    else:
        answer = "I can help search products, compare verified deals, inspect trust, check your wallet, or prepare a budget-safe cart."
    card = _product_card(product) if product else None
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

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.chat import ChatConversation, ChatMessage
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/chat", tags=["AI Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


def _product_card(product: Product) -> dict:
    return {"slug": product.slug, "name": product.name, "price": product.price, "image": product.image_url, "seller": product.seller_name, "trust": product.trust_score, "stock": product.stock_count}


@router.get("/history")
def history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversations = db.query(ChatConversation).filter(ChatConversation.user_id == current_user.id).order_by(ChatConversation.created_at.desc()).all()
    return [{"id": conversation.id, "title": conversation.title, "messages": [{"id": message.id, "role": message.role, "content": message.content, "card_type": message.card_type, "card": json.loads(message.card_payload) if message.card_payload else None, "created_at": message.created_at} for message in conversation.messages]} for conversation in conversations]


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

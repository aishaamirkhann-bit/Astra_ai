from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.messaging import DirectMessage, SellerConversation
from app.models.product import Product
from app.models.user import User
from app.realtime.messaging_ws import manager as messaging_events
from app.utils.helpers import as_aware_utc

router = APIRouter(prefix="/messaging", tags=["Seller-Buyer Messaging"])


class OpenConversationRequest(BaseModel):
    product_id: str


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class DirectMessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str
    content: str
    created_at: str | None


class ConversationOut(BaseModel):
    id: int
    other_id: int
    other_name: str
    other_role: str
    product_id: str | None
    product_title: str | None
    last_message: str | None
    last_message_at: str | None
    created_at: str | None


def _iso(value: datetime | None) -> str | None:
    return as_aware_utc(value).isoformat() if value else None


def _get_owned_conversation(db: Session, conversation_id: int, user: User) -> SellerConversation:
    conversation = db.get(SellerConversation, conversation_id)
    if conversation is None or user.id not in (conversation.buyer_id, conversation.seller_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _to_out(conversation: SellerConversation, user: User) -> ConversationOut:
    other = conversation.seller if user.id == conversation.buyer_id else conversation.buyer
    last = conversation.messages[-1] if conversation.messages else None
    return ConversationOut(
        id=conversation.id,
        other_id=other.id,
        other_name=other.name,
        other_role=other.role,
        product_id=conversation.product_id,
        product_title=conversation.product.title if conversation.product else None,
        last_message=last.content if last else None,
        last_message_at=_iso(conversation.last_message_at),
        created_at=_iso(conversation.created_at),
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversations = (
        db.query(SellerConversation)
        .filter(
            (SellerConversation.buyer_id == current_user.id)
            | (SellerConversation.seller_id == current_user.id)
        )
        .order_by(func.coalesce(SellerConversation.last_message_at, SellerConversation.created_at).desc(), SellerConversation.id.desc())
        .all()
    )
    return [_to_out(conversation, current_user) for conversation in conversations]


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def open_conversation(
    payload: OpenConversationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    seller = db.query(User).filter(User.name == product.seller_name, User.role == "seller").first()
    if seller is None:
        raise HTTPException(status_code=404, detail="This seller has no messaging account yet")
    if seller.id == current_user.id:
        raise HTTPException(status_code=400, detail="Sellers cannot message their own listing")

    conversation = (
        db.query(SellerConversation)
        .filter(
            SellerConversation.buyer_id == current_user.id,
            SellerConversation.seller_id == seller.id,
            SellerConversation.product_id == product.id,
        )
        .first()
    )
    if conversation is None:
        conversation = SellerConversation(buyer_id=current_user.id, seller_id=seller.id, product_id=product.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return _to_out(conversation, current_user)


@router.get("/conversations/{conversation_id}/messages", response_model=list[DirectMessageOut])
def message_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)
    return [
        DirectMessageOut(
            id=message.id,
            conversation_id=conversation.id,
            sender_id=message.sender_id,
            sender_name=message.sender.name,
            content=message.content,
            created_at=_iso(message.created_at),
        )
        for message in conversation.messages
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=DirectMessageOut, status_code=201)
async def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(db, conversation_id, current_user)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")
    message = DirectMessage(conversation_id=conversation.id, sender_id=current_user.id, content=content)
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    await messaging_events.broadcast(conversation.id, {
        "type": "message",
        "id": message.id,
        "conversation_id": conversation.id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": _iso(message.created_at),
    })
    return DirectMessageOut(
        id=message.id,
        conversation_id=conversation.id,
        sender_id=message.sender_id,
        sender_name=current_user.name,
        content=message.content,
        created_at=_iso(message.created_at),
    )

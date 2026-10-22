"""Meta WhatsApp Cloud API webhook: advisory catalogue discovery only."""
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.shopping_nlu import parse_shopping_intent
from app.services.buyer_tone import sense_buyer_tone
from app.services.localization import detect_locale, localized
from app.services.vision import analyze_image
from app.services.voice_service import ACCEPTED_AUDIO_MIME_TYPES, transcribe
from app.services.whatsapp_adapter import (
    download_meta_media,
    find_products,
    format_product_response,
    destination_country_from_phone,
    parse_webhook_messages,
    send_whatsapp_text,
    verify_meta_signature,
)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Commerce Adapter"])


@router.get("")
def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if not settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail="WhatsApp webhook verification is not configured")
    if mode == "subscribe" and verify_token and challenge and hmac.compare_digest(verify_token, settings.WHATSAPP_VERIFY_TOKEN):
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


async def _message_query(message) -> tuple[str, str | None]:
    """Return searchable text and a safe user-facing note, if processing lacked inputs."""
    if message.kind == "text":
        return message.text, None
    if not message.media_id:
        return message.text, "Media attachment ID was missing; please resend it or type your query."
    downloaded = await run_in_threadpool(download_meta_media, message.media_id)
    if not downloaded:
        return message.text, "Media processing is unavailable. Please type your product query."
    content, mime = downloaded
    mime = mime.split(";", 1)[0].strip().lower()
    if message.kind == "audio":
        if mime not in ACCEPTED_AUDIO_MIME_TYPES:
            return message.text, "This voice-note format is not supported. Please type your query."
        transcript = await run_in_threadpool(transcribe, content, mime)
        return " ".join(part for part in (message.text, transcript or "") if part).strip(), None if transcript else "Voice transcription is not configured. Please type your query."
    if message.kind == "image":
        visual = await run_in_threadpool(analyze_image, content, "whatsapp-image")
        query = " ".join(part for part in (message.text, visual.query if visual else "") if part).strip()
        return query, None if visual or message.text else "Image search is not available right now. Add a caption or type the product name."
    return message.text, "Please send a product name, voice note, or product photo."


@router.post("")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=503, detail="WhatsApp webhook signature verification is not configured")
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_meta_signature(raw_body, signature, settings.WHATSAPP_APP_SECRET):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp webhook signature")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from error
    messages = parse_webhook_messages(payload)
    outcomes = []
    for message in messages:
        query, note = await _message_query(message)
        locale = detect_locale(query)
        destination_country = destination_country_from_phone(message.sender)
        if query:
            intent = parse_shopping_intent(query)
            products = find_products(db, intent.normalized_query or query)
            reply = format_product_response(products, query, locale, destination_country)
        else:
            reply = f"Astra AI: {note or localized(locale, 'wa_empty')}"
        if note and query:
            reply = f"{reply}\n\nNote: {note}"
        tone = sense_buyer_tone(query, locale)
        if tone.assistance_prompt:
            reply = f"{reply}\n\n{tone.assistance_prompt}"
        outbound = False
        if settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
            outbound = await run_in_threadpool(send_whatsapp_text, message.sender, reply)
        outcomes.append({"message_id": message.message_id, "kind": message.kind,
                         "query": query[:500], "reply": reply, "outbound_sent": outbound,
                         "buyer_tone": tone.as_dict(), "locale": locale,
                         "advisory_only": True})
    # Meta delivers status/read notifications too; acknowledge them without actions.
    return {"accepted": True, "processed": len(outcomes), "messages": outcomes}

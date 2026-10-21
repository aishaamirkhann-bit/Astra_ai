"""Authenticated, read-only voice stream for live transcript/NLU updates.

The wire protocol accepts JSON transcript events and binary audio chunks. Audio
is buffered per connection and passed to the configured batch STT adapter on
``audio_end``; providers can replace this with a streaming adapter later.
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.services.shopping_nlu import intent_as_dict, parse_shopping_intent
from app.services.shopping_nlu import parse_regional_intent
from app.services.buyer_tone import sense_buyer_tone
from app.services.voice_service import ACCEPTED_AUDIO_MIME_TYPES, transcribe
from app.services.localization import detect_locale
from app.services.order_operations import parse_order_operation

router = APIRouter()
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_TRANSCRIPT_CHARS = 2000


def _authenticated_user_id(websocket: WebSocket) -> int | None:
    token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    try:
        user_id = int(claims["sub"]) if claims else 0
    except (KeyError, TypeError, ValueError):
        return None
    with SessionLocal() as db:
        return user_id if db.get(User, user_id) else None


def _user_locale(user_id: int) -> str:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return detect_locale("", user.preferred_language if user else None)


@router.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket):
    user_id = await asyncio.to_thread(_authenticated_user_id, websocket)
    if not user_id:
        await websocket.close(code=1008, reason="Valid access token required")
        return

    voice_locale = await asyncio.to_thread(_user_locale, user_id)

    await websocket.accept()
    audio = bytearray()
    audio_mime = "audio/webm"
    turns: list[str] = []
    context: dict[str, object] = {}
    output_generation = 0
    await websocket.send_json({
        "type": "ready",
        "channel": "voice",
        "mode": "read-only-advisory",
        "audio": "buffered-provider-adapter",
    })

    async def handle_transcript(text: str, final: bool) -> None:
        clean = text.strip()[:MAX_TRANSCRIPT_CHARS]
        if not clean:
            return
        intent = intent_as_dict(parse_shopping_intent(clean, voice_locale))
        regional_intent = parse_regional_intent(clean)
        buyer_tone = sense_buyer_tone(clean, voice_locale)
        order_operation = parse_order_operation(clean)
        if final:
            turns.append(clean)
            del turns[:-8]
            for key, value in intent.items():
                if key != "normalized_query" and value is not None:
                    context[key] = value
        await websocket.send_json({
            "type": "transcript",
            "text": clean,
            "final": final,
            "intent": intent,
            "regional_intent": regional_intent,
            "buyer_tone": buyer_tone.as_dict(),
            "order_operation": {"action": order_operation.action, "product_hint": order_operation.product_hint,
                                "request_type": order_operation.request_type, "advisory_only": True},
            "assistant_suggestion": buyer_tone.assistance_prompt,
            "context": dict(context),
            "mode": "read-only-advisory",
        })

    try:
        while True:
            event = await websocket.receive()
            if event["type"] == "websocket.connect":
                continue
            if event["type"] == "websocket.disconnect":
                break
            if event.get("bytes") is not None:
                chunk = event["bytes"]
                if len(audio) + len(chunk) > MAX_AUDIO_BYTES:
                    audio.clear()
                    await websocket.send_json({"type": "error", "code": "audio_too_large"})
                else:
                    audio.extend(chunk)
                continue
            raw = event.get("text")
            if raw is None:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "code": "invalid_json"})
                continue
            kind = payload.get("type")
            if kind == "interrupt":
                output_generation += 1
                # The bytes buffer contains the user's new turn, so preserve
                # it while invalidating any stale assistant output generation.
                await websocket.send_json({"type": "interrupted", "generation": output_generation})
            elif kind == "transcript":
                text = payload.get("text")
                if isinstance(text, str):
                    await handle_transcript(text, bool(payload.get("final")))
            elif kind == "audio_start":
                audio.clear()
                mime = payload.get("mime")
                if isinstance(mime, str) and mime.split(";", 1)[0].strip() in ACCEPTED_AUDIO_MIME_TYPES:
                    audio_mime = mime.split(";", 1)[0].strip()
                await websocket.send_json({"type": "listening"})
            elif kind == "audio_end":
                if audio:
                    clip = bytes(audio)
                    audio.clear()
                    transcript = await asyncio.to_thread(transcribe, clip, audio_mime)
                    if transcript:
                        await handle_transcript(transcript, True)
                    else:
                        await websocket.send_json({"type": "stt_unavailable"})
                await websocket.send_json({"type": "audio_processed"})
    except WebSocketDisconnect:
        audio.clear()

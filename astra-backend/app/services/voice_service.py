"""
PATH: astra-backend/app/services/voice_service.py  (REPLACE — same interface
you already built, transcribe()/synthesize() signatures unchanged, only the
actual HTTP call in transcribe() is fixed)

BUG in your current version: it POSTs JSON {"audio": base64, "mime": ...} to
    https://api.{STT_PROVIDER}.com/v1/listen
This does not match Groq's real transcription API — Groq's endpoint is
    https://api.groq.com/openai/v1/audio/transcriptions
and it requires a multipart/form-data file upload (like OpenAI's Whisper
API), not a JSON body with base64 audio. As written, when STT_PROVIDER="groq"
every call fails and silently falls back to the placeholder transcript —
your GROQ_API_KEY is never actually used for STT either.

synthesize() is left as-is (returns None) — correctly, since Groq's TTS
(Orpheus) is a paid tier, not free; nothing to wire here for the free setup.
"""
import json
import logging
import mimetypes
import urllib.error
import urllib.request

from app.core.config import settings

logger = logging.getLogger("astra.voice")

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
ACCEPTED_AUDIO_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/webm"}


def transcribe(audio_bytes: bytes, mime: str) -> str | None:
    """Call Groq's real Whisper transcription endpoint. Returns None when
    unset/unsupported (or on any provider error) so the caller falls back
    to the existing deterministic placeholder string.
    """
    if not settings.STT_API_KEY or settings.STT_PROVIDER != "groq":
        return None
    if mime not in ACCEPTED_AUDIO_MIME_TYPES:
        return None

    boundary = "astra-voice-boundary"
    ext = mimetypes.guess_extension(mime) or ".webm"
    body = b"".join([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{GROQ_WHISPER_MODEL}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio{ext}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n".encode(),
        audio_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        GROQ_TRANSCRIPTION_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.STT_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.PRODUCT_PROVIDER_TIMEOUT_SECONDS) as response:
            body_json = json.loads(response.read().decode("utf-8"))
        transcript = body_json.get("text", "").strip()
        if not transcript:
            raise ValueError("STT provider returned no transcript")
        return transcript
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
        logger.warning("STT provider call failed, falling back to placeholder transcript: %s", error)
        return None


def synthesize(text: str) -> bytes | None:
    """Always returns None — Groq's TTS (Orpheus) is a paid Developer-tier
    feature, not part of the free setup. Use the browser's built-in
    speechSynthesis on the frontend for spoken replies instead.
    """
    return None
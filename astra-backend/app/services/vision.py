"""Vision-provider integration used by image search and multimodal chat."""

import base64
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import settings

logger = logging.getLogger("astra.vision")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_VISION_MODEL = "qwen/qwen3.8-27b"
_VISION_PROMPT = (
    "Describe the visible retail product for catalog search. Return JSON only with "
    "string fields category, color, style, pattern and a keywords array of at most "
    "6 short strings. Use empty strings or an empty array when uncertain. Do not "
    "guess brand, material, size, or details not clearly visible."
)
_ROOM_PROMPT = (
    "Inspect this room photo for interior styling. Return JSON only with string fields "
    "wall_color_tones, ambient_lighting, visible_layout, furniture_aesthetic, "
    "possible_space_constraints, and confidence_note. Describe only visible clues. "
    "Do not estimate measurements, exact dimensions, hidden walls, or camera depth. "
    "Write descriptive values in the requested language when possible. Locale: {locale}."
)


@dataclass
class VisionResult:
    """Structured output of an image analysis call."""

    labels: list[str] = field(default_factory=list)
    query: str = ""
    confidence: float = 0.0
    provider: str = ""


@dataclass(frozen=True)
class ChatVisionResult:
    """Chat image-analysis outcome without exposing provider errors to clients."""

    status: Literal["analyzed", "not_configured", "provider_error"]
    answer: str | None = None


def _vision_is_configured() -> bool:
    provider = settings.VISION_PROVIDER.strip().lower() or "groq"
    return provider == "groq" and bool(settings.VISION_API_KEY or settings.GROQ_API_KEY)


def _vision_api_key() -> str:
    return settings.VISION_API_KEY or settings.GROQ_API_KEY


def _request_vision_completion(
    image_bytes: bytes,
    content_type: str,
    prompt: str,
    *,
    temperature: float,
    max_tokens: int,
) -> str | None:
    if not _vision_is_configured():
        return None

    data_url = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    payload = json.dumps({
        "model": settings.VISION_MODEL or DEFAULT_GROQ_VISION_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }).encode("utf-8")
    request = urllib.request.Request(
        GROQ_CHAT_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {_vision_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.VISION_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        answer = body["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("vision provider returned an empty answer")
        return answer.strip()
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, IndexError) as error:
        logger.warning("Groq vision request failed (%s)", type(error).__name__)
        return None


def analyze_image(image_bytes: bytes, filename: str = "") -> VisionResult | None:
    """Extract conservative visual descriptors, or return None for text fallback."""
    del filename  # Never infer image content from a user-controlled filename.
    content_type = sniff_image_type(image_bytes)
    if content_type is None:
        return None

    text = _request_vision_completion(
        image_bytes,
        content_type,
        _VISION_PROMPT,
        temperature=0.1,
        max_tokens=40,
    )
    if text is None:
        return None

    try:
        descriptors = json.loads(text)
        if not isinstance(descriptors, dict):
            return None
        allowed = ("category", "color", "style", "pattern")
        values = [descriptors.get(key, "") for key in allowed]
        keywords = descriptors.get("keywords", [])
        if any(not isinstance(value, str) for value in values) or not isinstance(keywords, list):
            return None
        values += [value for value in keywords[:6] if isinstance(value, str)]
        labels = list(dict.fromkeys(
            " ".join(value.lower().split()[:4])[:60]
            for value in values if value.strip()
        ))
    except (json.JSONDecodeError, TypeError, AttributeError):
        # An unexpected provider format is treated as unavailable rather than
        # turning arbitrary prose into catalog claims.
        return None
    query = " ".join(labels)
    if not labels:
        return None
    return VisionResult(labels=labels, query=query, confidence=0.75, provider="groq")


def analyze_room_image(image_bytes: bytes, locale: str = "en") -> dict | None:
    """Conservatively extract visible room styling cues; never infer dimensions."""
    content_type = sniff_image_type(image_bytes)
    if content_type is None:
        return None
    text = _request_vision_completion(
        image_bytes, content_type, _ROOM_PROMPT.format(locale=locale),
        temperature=0.1, max_tokens=240,
    )
    if text is None:
        return None
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    fields = ("wall_color_tones", "ambient_lighting", "visible_layout", "furniture_aesthetic", "possible_space_constraints", "confidence_note")
    if not isinstance(result, dict):
        return None
    return {field: str(result.get(field, ""))[:300] for field in fields}


def sniff_image_type(image_bytes: bytes) -> str | None:
    """Return an allowed MIME type only for a structurally plausible image."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        saw_header = saw_end = False
        compressed = bytearray()
        while offset + 12 <= len(image_bytes):
            length = int.from_bytes(image_bytes[offset:offset + 4], "big")
            end = offset + 12 + length
            if end > len(image_bytes):
                return None
            chunk_type = image_bytes[offset + 4:offset + 8]
            chunk = image_bytes[offset + 8:offset + 8 + length]
            crc = int.from_bytes(image_bytes[offset + 8 + length:end], "big")
            import zlib
            if zlib.crc32(chunk_type + chunk) & 0xFFFFFFFF != crc:
                return None
            if not saw_header:
                if chunk_type != b"IHDR" or length != 13:
                    return None
                width = int.from_bytes(chunk[:4], "big")
                height = int.from_bytes(chunk[4:8], "big")
                if width < 1 or height < 1 or width * height > 40_000_000:
                    return None
                saw_header = True
            if chunk_type == b"IDAT":
                compressed.extend(chunk)
            if chunk_type == b"IEND":
                if length != 0 or end != len(image_bytes):
                    return None
                saw_end = True
                break
            offset = end
        if saw_header and saw_end and compressed:
            try:
                import zlib
                zlib.decompress(compressed)
                return "image/png"
            except zlib.error:
                return None
        return None
    if image_bytes.startswith(b"RIFF") and len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
        declared = int.from_bytes(image_bytes[4:8], "little") + 8
        return "image/webp" if declared == len(image_bytes) and len(image_bytes) >= 20 else None
    if image_bytes.startswith(b"\xff\xd8") and image_bytes.endswith(b"\xff\xd9"):
        # Require a frame header and scan marker as well as SOI/EOI.
        return "image/jpeg" if b"\xff\xc0" in image_bytes or b"\xff\xc2" in image_bytes else None
    return None


def describe_image_for_chat(
    image_bytes: bytes,
    content_type: str,
    prompt: str,
    locale: str = "en",
) -> ChatVisionResult:
    """Answer a chat prompt about an image and report actionable failure state."""
    if not _vision_is_configured():
        return ChatVisionResult(status="not_configured")

    question = prompt.strip() or "Describe what you can see and suggest useful ideas."
    language_names = {"ur": "Urdu", "roman_urdu": "Roman Urdu using Latin script", "pa": "Punjabi", "ps": "Pashto", "sd": "Sindhi", "fa": "Persian (Farsi)", "zh": "Simplified Chinese", "ar": "Arabic", "en": "English"}
    request_prompt = (
        "Answer the user's question helpfully using only visible details. "
        "For rooms, suggest practical decor ideas; for clothing, comment on "
        "visible styling and coordination without identifying the person; "
        "for products, describe visible features. Do not claim certainty "
        "about details that cannot be seen. Reply in the exact requested language/locale: "
        + language_names.get(locale, "English") + ". User question: " + question
    )
    answer = _request_vision_completion(
        image_bytes,
        content_type,
        request_prompt,
        temperature=0.3,
        max_tokens=400,
    )
    if answer is None:
        return ChatVisionResult(status="provider_error")
    return ChatVisionResult(status="analyzed", answer=answer)

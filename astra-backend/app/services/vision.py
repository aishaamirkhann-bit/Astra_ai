"""
PATH: astra-backend/app/services/vision.py  (REPLACE — same interface you already
built, VisionResult dataclass unchanged, only the actual HTTP call is fixed)

BUG in your current version: it POSTs to
    https://api.{VISION_PROVIDER}.com/v1/vision/analyze
    body: {"model": ..., "image": base64, "filename": ...}
This URL/body shape does not exist for ANY real provider — when
VISION_PROVIDER="groq", the real endpoint is Groq's OpenAI-compatible
chat-completions endpoint with an image_url message, not a made-up
/v1/vision/analyze route. As written, every call 404s, silently falls
back to None, and your GROQ_API_KEY is never actually used for vision.
This version keeps your exact VisionResult contract but calls the real
Groq endpoint.
"""
import base64
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger("astra.vision")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_VISION_PROMPT = (
    "Identify the single product category and product type shown in this "
    "image as 2-4 lowercase words suitable for a product search query "
    "(e.g. 'gaming laptop', 'wireless earbuds', 'samsung smartphone'). "
    "Reply with ONLY those words, nothing else, no punctuation."
)


@dataclass
class VisionResult:
    """Structured output of an image analysis call."""

    labels: list[str] = field(default_factory=list)
    query: str = ""
    confidence: float = 0.0
    provider: str = ""


def analyze_image(image_bytes: bytes, filename: str = "") -> VisionResult | None:
    """Call the configured vision provider. Returns None when unset/unsupported
    (or on any provider error) so callers fall back to the filename-guess path.
    """
    if not settings.VISION_API_KEY or settings.VISION_PROVIDER != "groq":
        return None

    content_type = "image/jpeg"
    if filename.endswith(".png"):
        content_type = "image/png"
    elif filename.endswith(".webp"):
        content_type = "image/webp"

    data_url = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    payload = json.dumps({
        "model": settings.VISION_MODEL or "llama-3.2-90b-vision-preview",
        "temperature": 0.1,
        "max_tokens": 20,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }).encode("utf-8")

    request = urllib.request.Request(
        GROQ_CHAT_URL,
        data=payload,
        headers={"Authorization": f"Bearer {settings.VISION_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.VISION_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"].strip().lower()
        labels = [word for word in text.split() if word]
        if not labels:
            raise ValueError("vision provider returned no labels")
        return VisionResult(labels=labels, query=text, confidence=0.75, provider="groq")
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
        logger.warning("vision provider call failed, falling back to filename guess: %s", error)
        return None
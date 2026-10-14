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
    """Identify an image for Explore search, or return None for its fallback path."""
    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".webp"):
        content_type = "image/webp"

    text = _request_vision_completion(
        image_bytes,
        content_type,
        _VISION_PROMPT,
        temperature=0.1,
        max_tokens=40,
    )
    if text is None:
        return None

    query = text.lower()
    labels = [word for word in query.split() if word]
    if not labels:
        return None
    return VisionResult(labels=labels, query=query, confidence=0.75, provider="groq")


def describe_image_for_chat(
    image_bytes: bytes,
    content_type: str,
    prompt: str,
) -> ChatVisionResult:
    """Answer a chat prompt about an image and report actionable failure state."""
    if not _vision_is_configured():
        return ChatVisionResult(status="not_configured")

    question = prompt.strip() or "Describe what you can see and suggest useful ideas."
    request_prompt = (
        "Answer the user's question helpfully using only visible details. "
        "For rooms, suggest practical decor ideas; for clothing, comment on "
        "visible styling and coordination without identifying the person; "
        "for products, describe visible features. Do not claim certainty "
        "about details that cannot be seen. User question: " + question
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

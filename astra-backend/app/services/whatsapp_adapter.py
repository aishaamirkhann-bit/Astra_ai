"""WhatsApp webhook parsing, safe catalogue discovery, and Graph API adapters."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any
from urllib.parse import quote
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product import Product
from app.services.shopping_nlu import parse_shopping_intent
from app.services.localization import cross_border_advisory, detect_locale, localized

MAX_MEDIA_BYTES = 8 * 1024 * 1024
ALLOWED_MEDIA_HOSTS = {"lookaside.fbsbx.com", "lookaside.whatsapp.net", "mmg.whatsapp.net"}
_STOPWORDS = {"the", "for", "and", "with", "under", "pkr", "rs", "mein", "milega", "milega", "chahiye", "please", "show", "find", "want", "buy", "yeh", "ye", "kya", "hai", "mein"}


@dataclass(frozen=True)
class WhatsAppMessage:
    message_id: str
    sender: str
    kind: str
    text: str = ""
    media_id: str = ""
    mime_type: str = ""


def parse_webhook_messages(payload: dict[str, Any]) -> list[WhatsAppMessage]:
    """Extract supported Meta message shapes without trusting media URLs."""
    result = []
    entries = payload.get("entry", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return result
    for entry in entries:
        changes = entry.get("changes", []) if isinstance(entry, dict) else []
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value", {}) if isinstance(change, dict) else {}
            incoming = value.get("messages", []) if isinstance(value, dict) else []
            if not isinstance(incoming, list):
                continue
            for message in incoming:
                if not isinstance(message, dict):
                    continue
                sender = str(message.get("from", ""))[:32]
                message_id = str(message.get("id", ""))[:160]
                kind = str(message.get("type", ""))
                body = ""
                media_id = ""
                mime = ""
                if kind == "text":
                    body = str((message.get("text") or {}).get("body", ""))[:2000]
                elif kind in {"image", "audio", "voice"}:
                    media = message.get(kind, {}) or {}
                    media_id = str(media.get("id", ""))[:200]
                    mime = str(media.get("mime_type", ""))[:100].lower()
                    body = str(media.get("caption", ""))[:500]
                    kind = "audio" if kind == "voice" else kind
                elif kind == "interactive":
                    interactive = message.get("interactive") or {}
                    reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
                    body = str(reply.get("title") or reply.get("id") or "")[:500]
                    kind = "text"
                else:
                    continue
                if sender and message_id:
                    result.append(WhatsAppMessage(message_id, sender, kind, body.strip(), media_id, mime))
    return result


def verify_meta_signature(body: bytes, signature: str, app_secret: str) -> bool:
    if not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def find_products(db: Session, query: str, limit: int = 3) -> list[Product]:
    intent = parse_shopping_intent(query)
    normalized = intent.normalized_query or query.lower()
    terms = {term for term in re.findall(r"[a-z0-9]+", normalized) if len(term) > 2 and term not in _STOPWORDS}
    products = db.query(Product).filter(Product.listing_status == "active", Product.stock_count > 0).all()
    ranked = []
    for product in products:
        text = f"{product.title} {product.category} {product.subcategory} {product.search_terms} {product.color}".lower()
        score = sum(term in text for term in terms)
        if intent.category:
            category = intent.category.lower()
            if category in product.category.lower() or (category == "clothing & fashion" and "fashion" in product.category.lower()):
                score += 2
        if intent.color and intent.color.lower() in (product.color or "").lower():
            score += 2
        if intent.budget_max is not None and product.base_price > intent.budget_max:
            continue
        if score:
            ranked.append((score, float(product.rating or 0), product))
    ranked.sort(key=lambda item: (item[0], item[1], item[2].id), reverse=True)
    return [product for _, _, product in ranked[:max(1, min(limit, 5))]]


def product_review_url(product_id: str) -> str:
    # Product view only. It carries no auth/session/payment token and starts no checkout.
    return f"{settings.FRONTEND_ORIGIN.rstrip('/')}/product/{quote(product_id, safe='')}?ref=whatsapp"


def destination_country_from_phone(phone: str) -> str | None:
    """Best-effort calling-code hint only; buyer must confirm delivery country."""
    digits = re.sub(r"\D", "", phone or "")
    for prefix, country in (("971", "AE"), ("86", "CN"), ("98", "IR"), ("92", "PK")):
        if digits.startswith(prefix):
            return country
    return None


def format_product_response(products: list[Product], query: str, locale: str | None = None,
                            destination_country: str | None = None) -> str:
    language = detect_locale(query, locale)
    if not products:
        return f"Astra AI: {localized(language, 'wa_empty')}"
    lines = [localized(language, "wa_intro")]
    for index, product in enumerate(products, 1):
        lines.append(f"{index}. {product.title} - PKR {product.base_price:,.0f} | Trust indicator {product.trust}%\n{product_review_url(product.id)}")
        advisory = cross_border_advisory(product.origin_country or "PK", destination_country,
                                         product.base_price, language)
        if advisory:
            lines.append(advisory["message"])
    if destination_country:
        lines.append(localized(language, "wa_country_hint"))
    lines.append(localized(language, "wa_safety"))
    return "\n".join(lines)[:4000]

def download_meta_media(media_id: str) -> tuple[bytes, str] | None:
    """Download media through Meta's authenticated ID endpoint with host/size checks."""
    if not settings.WHATSAPP_ACCESS_TOKEN or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", media_id):
        return None
    endpoint = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{quote(media_id, safe='')}"
    request = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            metadata = json.loads(response.read(64 * 1024).decode("utf-8"))
        media_url = metadata.get("url")
        from urllib.parse import urlparse
        parsed = urlparse(media_url or "")
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_MEDIA_HOSTS:
            return None
        request = urllib.request.Request(media_url, headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"})
        with urllib.request.urlopen(request, timeout=15) as response:
            content_type = response.headers.get_content_type().lower()
            data = response.read(MAX_MEDIA_BYTES + 1)
        if len(data) > MAX_MEDIA_BYTES:
            return None
        return data, content_type
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError):
        return None


def send_whatsapp_text(recipient: str, text: str) -> bool:
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        return False
    payload = json.dumps({"messaging_product": "whatsapp", "recipient_type": "individual",
                          "to": recipient, "type": "text", "text": {"preview_url": False, "body": text[:4000]}}).encode()
    endpoint = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{quote(settings.WHATSAPP_PHONE_NUMBER_ID, safe='')}/messages"
    request = urllib.request.Request(endpoint, data=payload, headers={
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False

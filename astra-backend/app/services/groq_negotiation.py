"""Optional Groq seller-agent decisions with a safe rules fallback."""
import json
import logging
import urllib.request

from app.core.config import settings

logger = logging.getLogger("astra.negotiation")


def request_groq_decision(context: dict) -> dict | None:
    if not settings.GROQ_API_KEY:
        return None
    prompt = (
        "Act as a seller negotiation agent. Return JSON only with keys status "
        "(accepted, counter, or rejected), counter_offer (number or null), and "
        "reasoning (array of short strings). Never counter below seller_floor. "
        f"Context: {json.dumps(context)}"
    )
    payload = json.dumps({
        "model": settings.GROQ_MODEL, "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.GROQ_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        decision = json.loads(body["choices"][0]["message"]["content"])
        if decision.get("status") not in {"accepted", "counter", "rejected"} or not isinstance(decision.get("reasoning"), list):
            raise ValueError("invalid Groq negotiation response")
        return decision
    except Exception as exc:
        logger.warning("Groq unavailable; using negotiation rules: %s", exc)
        return None

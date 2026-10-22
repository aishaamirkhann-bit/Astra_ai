"""Deterministic buyer-tone cues for optional, non-binding assistance."""
from dataclasses import asdict, dataclass
import re

from app.services.shopping_nlu import normalize_shopping_text
from app.services.localization import detect_locale, localized


@dataclass(frozen=True)
class BuyerTone:
    category: str
    confidence: float
    signals: tuple[str, ...]
    assistance_prompt: str | None

    def as_dict(self) -> dict:
        value = asdict(self)
        value["signals"] = list(self.signals)
        value["advisory_only"] = True
        return value


_CUES = {
    "price_sensitive": (
        r"\b(?:too expensive|very expensive|expensive|too costly|price is high|high price|"
        r"bohot mehnga|bohat mehnga|mehnga hai|mehngi hai|qeemat.{0,12}grana|"
        r"price.{0,12}(?:expensive|discount|kam)|very mehngo|ghano mehngo|cheap|sasta|sasto|"
        r"rate.{0,12}(?:kam|discount)|(?:kam|discount).{0,12}rate|"
        r"budget.{0,12}(?:low|limited|tight)|afford)\b",
        "I can show lower-priced options or prepare a non-binding offer that respects each seller’s price floor. You review the final total and authorize any purchase at checkout.",
    ),
    "hesitant": (
        r"\b(?:not sure|confused|uncertain|help me decide|which size|what size|"
        r"size.{0,15}(?:nahi pata|not sure|confused)|samajh.{0,12}nahi|pata nahi|"
        r"kaunsa loon|kaunsi loon|na pohegam|samjhan mushkil)\b",
        "Would a size guide or a quick comparison help? Tell me your usual fit and I can show the available options.",
    ),
    "high_intent": (
        r"\b(?:ready to buy|buy now|order now|place my order|abhi khareedna|"
        r"abhi khareed|abhi lena|hun laina|os akhlam)\b",
        "Ready when you are. Open the product to review the item and final total; checkout will ask you to explicitly authorize the purchase.",
    ),
}


def sense_buyer_tone(text: str, locale: str | None = None) -> BuyerTone:
    """Detect explicit language cues only; this is not a psychological diagnosis."""
    normalized = normalize_shopping_text(text or "")
    for category in ("price_sensitive", "hesitant", "high_intent"):
        pattern, _prompt = _CUES[category]
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            key = {"price_sensitive": "tone_price", "hesitant": "tone_hesitant", "high_intent": "tone_intent"}[category]
            return BuyerTone(category, 0.82, (match.group(0),), localized(detect_locale(text, locale), key))
    return BuyerTone("neutral", 0.0, (), None)

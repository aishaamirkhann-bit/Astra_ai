"""Deterministic extraction of shopping constraints from English, Roman Urdu,
and common Urdu-script phrases. This module never performs commerce actions.
"""
from dataclasses import dataclass
import re
import unicodedata
from app.services.localization import normalize_multilingual_text


_URDU_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_URDU_PHRASES = {
    "میرا بجٹ": "mera budget",
    "میری بجٹ": "mera budget",
    "سے کم": "se kam",
    "مجھے": "mujhe",
    "قمیض": "shirt",
    "شرٹ": "shirt",
    "فارمل": "formal",
    "چاہیے": "chahiye",
    "میڈیم": "medium",
    "درمیانہ": "medium",
    "چھوٹا": "small",
    "چھوٹی": "small",
    "بڑا": "large",
    "بڑی": "large",
    "سائز": "size",
    "رنگ": "color",
    "لال": "red",
    "سرخ": "red",
    "نیلا": "blue",
    "نیلی": "blue",
    "کالا": "black",
    "کالی": "black",
    "سیاہ": "black",
    "سفید": "white",
    "سبز": "green",
    "گلابی": "pink",
    "جامنی": "purple",
    "میرا": "mera",
    "بجٹ": "budget",
    "ہے": "hai",
    "روپے": "pkr",
    "پسند": "pasand",
    "میرا پسندیدہ": "mera favorite",
    "میری پسندیدہ": "meri favorite",
    "پسندیدہ": "favorite",
    "تک": "tak",
}
_ROMAN_ALIASES = {
    "laal": "red", "surkh": "red", "neela": "blue", "neeli": "blue",
    "kala": "black", "kali": "black", "siyah": "black", "safed": "white",
    "hara": "green", "hari": "green", "gulabi": "pink", "jamni": "purple",
    "darmiyana": "medium", "darmiyani": "medium", "chhota": "small",
    "chhoti": "small", "bara": "large", "bari": "large", "qameez": "shirt",
    "kameez": "shirt", "rang": "color", "size": "size",
}
_REGIONAL_ALIASES = {
    # Punjabi shopping phrases (Punjabi is lexical here; ASR remains provider-owned).
    "sohnra": "beautiful", "sohna": "beautiful", "suhna": "beautiful",
    "vadiya": "beautiful", "changa": "good",
    # Pashto phrases.
    "khaista": "beautiful", "jora": "dress",
    "tor": "black", "spin": "white", "shna": "green", "grana": "expensive",
    # Sindhi phrases.
    "sutho": "beautiful", "surkho": "red", "karo": "black",
    "sasto": "cheap", "ghano": "very",
    # Regional negotiation/style words normalize to existing search vocabulary.
    "ghatao": "discount", "ghataayo": "discount", "ghat": "discount",
    "qeemat": "price", "bhaao": "price",
    "shaadi": "wedding", "wade": "wedding", "festive": "festive",
}
_DIALECT_MARKERS = {
    "Punjabi": {"sohnra", "sohna", "suhna", "vadiya", "changa"},
    "Pashto": {"khaista", "jora", "tor", "spin", "shna", "grana"},
    "Sindhi": {"sutho", "surkho", "karo", "sasto", "ghano", "bhaao"},
}
_COLORS = {
    "red": "red", "blue": "blue", "black": "black", "white": "white",
    "green": "green", "pink": "pink", "purple": "purple", "yellow": "yellow",
    "brown": "brown", "gray": "gray", "grey": "gray", "orange": "orange",
}
_SIZES = {
    "extra small": "XS", "x small": "XS", "xs": "XS", "small": "S",
    "medium": "M", "med": "M", "large": "L", "extra large": "XL",
    "x large": "XL", "xl": "XL", "xxl": "XXL", "2xl": "XXL",
}
_CATEGORIES = (
    (("formal shirt", "shirt", "shirts", "suit", "suits", "qameez", "kameez", "clothes", "clothing", "fashion", "kapray", "kurti", "dress", "dresses", "formal wear"), "Clothing & Fashion"),
    (("laptop", "notebook", "computer", "macbook"), "Laptops & Computers"),
    (("headphone", "earbud", "speaker", "audio"), "Audio & Wearables"),
    (("smartphone", "mobile", "phone", "iphone"), "Mobiles"),
    (("makeup", "lipstick", "beauty", "skincare"), "Makeup & Beauty"),
    (("jewelry", "jewellery", "earring", "necklace", "ring"), "Jewelry"),
    (("furniture", "chair", "sofa", "table"), "Furniture"),
)
_SAFE_PREFERENCE_TERMS = (
    "cotton", "linen", "formal", "casual", "lightweight", "durable", "wireless",
    "noise cancelling", "eco friendly", "minimalist", "modest", "waterproof", "wedding", "festive", "traditional",
)
_AMOUNT = r"(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>k|thousand|lac|lakh)?"
_NUMBER = r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lac|lakh)?"
_RANGE = re.compile(
    rf"(?:between|from|budget range(?: is)?|mera budget(?: range)?(?: hai)?|my budget range(?: is)?)\s*"
    rf"(?:pkr|rs\.?|rupees)?\s*{_NUMBER}\s*(?:to|and|se|[-–])\s*"
    rf"(?:pkr|rs\.?|rupees)?\s*{_NUMBER}", re.IGNORECASE,
)
_BUDGET_VALUE = re.compile(
    rf"(?:my budget(?: is)?|mera budget(?: hai)?|budget(?: is)?)\s*(?:pkr|rs\.?|rupees)?\s*{_AMOUNT}",
    re.IGNORECASE,
)
_BUDGET_BOUND = re.compile(
    rf"(?:under|below|less than|up to|upto|maximum|max|se kam|tak)\s*(?:pkr|rs\.?|rupees)?\s*{_NUMBER}"
    rf"|{_NUMBER}\s*(?:pkr|rs\.?|rupees)?\s*(?:se kam|tak|under|below|or less)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ShoppingIntent:
    category: str | None = None
    color: str | None = None
    size: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    normalized_query: str = ""

    def public_constraints(self) -> dict[str, str | float | None]:
        return {
            "category": self.category,
            "color": self.color,
            "size": self.size,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
        }


def normalize_shopping_text(text: str, locale: str | None = None) -> str:
    normalized = normalize_regional_text(normalize_multilingual_text(text, locale)).translate(_URDU_DIGITS).lower().replace(",", "")
    for source in sorted(_URDU_PHRASES, key=len, reverse=True):
        normalized = normalized.replace(source, f" {_URDU_PHRASES[source]} ")
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?|[^\W\d_]+", normalized, flags=re.UNICODE)
    return " ".join(_ROMAN_ALIASES.get(word, word) for word in words)


_GREETING_WORDS = {
    "hi", "hello", "hey", "salaam", "salam", "assalam", "aoa", "asalamualaikum",
    "assalamualaikum", "walaikum", "alaikum", "marhaba", "ahlan", "namaste", "sat", "sri", "akal", "o",
}


_GREETING_REPLIES = {
    "en": "Hello! Welcome to Astra AI. How can I assist you with your shopping today?",
    "ur": "\u0648\u0639\u0644\u06cc\u06a9\u0645 \u0627\u0644\u0633\u0644\u0627\u0645! \u0627\u0633\u0679\u0631\u0627 \u0627\u06cc \u0622\u0626\u06cc \u0645\u06cc\u06ba \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f. \u0622\u062c \u0645\u06cc\u06ba \u0622\u067e \u06a9\u06cc \u0634\u0627\u067e\u0646\u06af \u06cc\u0627 \u0645\u0634\u0648\u0631\u06d2 \u0645\u06cc\u06ba \u06a9\u06cc\u0633\u06d2 \u0645\u062f\u062f \u06a9\u0631 \u0633\u06a9\u062a\u0627 \u06c1\u0648\u06ba\u061f",
    "roman_urdu": "Walaikum Assalam! Astra AI mein aapka khushamdeed. Main aapki kya madad karoon?",
    "pa": "Sat sri akal! Astra AI vich tuhadda swagat hai. Aj shopping ya mashware layi ki madad karaan?",
    "ps": "\u0648\u0627\u0644\u064a\u06a9\u0645 \u0627\u0644\u0633\u0644\u0627\u0645! \u0627\u0633\u062a\u0631\u0627 \u0627\u06cc \u0622\u0626\u06cc \u062a\u0647 \u0631\u0627\u063a\u0644\u0627\u0633\u062a. \u062f \u0634\u0627\u067e\u0646\u06af \u06cc\u0627 \u0645\u0634\u0648\u0631\u06d2 \u067e\u0647 \u0628\u0627\u0631\u0647 \u06a9\u06d0 \u0685\u0647 \u0645\u0631\u0633\u062a\u0647 \u0648\u06a9\u0693\u0645\u061f",
    "sd": "\u0648\u0639\u0644\u064a\u06aa\u0645 \u0627\u0644\u0633\u0644\u0627\u0645! \u0627\u0633\u0679\u0631\u0627 \u0627\u064a\u0621 \u0622\u0626\u064a \u0645\u064a\u0646 \u062a\u0648\u0647\u0627\u0646 \u062c\u0648 \u062e\u0648\u0634 \u0622\u0645\u062f\u064a\u062f. \u0686\u0627 \u062a\u0648\u0647\u0627\u0646 \u06a9\u064a \u0634\u0627\u067e\u0646\u06af \u064a\u0627 \u0645\u0634\u0648\u0631\u064a \u0645\u064a\u0646 \u0645\u062f\u062f \u06aa\u0631\u064a\u0627\u0646\u061f",
    "fa": "\u0633\u0644\u0627\u0645! \u0648\u0642\u062a \u0628\u062e\u06cc\u0631. \u0686\u06af\u0648\u0646\u0647 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u0645 \u0628\u0647 \u0634\u0645\u0627 \u06a9\u0645\u06a9 \u06a9\u0646\u0645\u061f",
    "zh": "\u4f60\u597d\uff01\u6b22\u8fce\u4f7f\u7528 Astra AI\u3002\u8bf7\u95ee\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u60a8\uff1f",
    "ar": "\u0648\u0639\u0644\u064a\u0643\u0645 \u0627\u0644\u0633\u0644\u0627\u0645! \u0645\u0631\u062d\u0628\u0627\u064b \u0628\u0643 \u0641\u064a Astra AI. \u0643\u064a\u0641 \u0623\u0633\u0627\u0639\u062f\u0643 \u0627\u0644\u064a\u0648\u0645\u061f \u0647\u0644 \u062a\u0631\u064a\u062f \u0627\u0644\u0628\u062d\u062b \u0639\u0646 \u0645\u0646\u062a\u062c\u060c \u0623\u0645 \u0642\u0627\u0631\u0646\u0629 \u0627\u0644\u062e\u064a\u0627\u0631\u0627\u062a\u061f",
}


def detect_greeting(text: str) -> bool:
    """Recognize short greetings without interpreting them as catalog searches."""
    value = unicodedata.normalize("NFKC", text or "").lower().strip()
    if "\u0a38\u0a24 \u0a38\u0a4d\u0a30\u0a40 \u0a05\u0a15\u0a3e\u0a32" in value:
        return True
    if any(token in value for token in (
        "\u4f60\u597d", "\u60a8\u597d", "\u0645\u0631\u062d\u0628\u0627",
        "\u0627\u0644\u0633\u0644\u0627\u0645 \u0639\u0644\u064a\u0643\u0645",
        "\u0633\u0644\u0627\u0645", "\u06c1\u06cc\u0644\u0648",
    )):
        return True
    words = set(re.findall(r"[a-z]+", value))
    return bool(words and words <= _GREETING_WORDS and len(words) <= 5)


def greeting_response(locale: str | None) -> str:
    """Return a warm, deterministic greeting in a supported active locale."""
    from app.services.localization import normalize_locale

    return _GREETING_REPLIES.get(normalize_locale(locale), _GREETING_REPLIES["en"])


_PRODUCT_MATCH_REPLIES = {
    "en": "I found matching in-stock options. I ranked them by fit and trust; compare each listing's current price and customer rating below.",
    "ur": "\u0645\u06cc\u06ba \u0646\u06d2 \u0622\u067e \u06a9\u06cc \u0636\u0631\u0648\u0631\u062a \u06a9\u06d2 \u0645\u0637\u0627\u0628\u0642 \u062f\u0633\u062a\u06cc\u0627\u0628 \u0645\u0635\u0646\u0648\u0639\u0627\u062a \u062a\u0644\u0627\u0634 \u06a9\u06cc \u06c1\u06cc\u06ba\u06d4 \u0646\u062a\u0627\u0626\u062c \u06a9\u0648 \u0645\u0646\u0627\u0633\u0628\u062a \u0627\u0648\u0631 \u0627\u0639\u062a\u0628\u0627\u0631 \u06a9\u06cc \u0628\u0646\u06cc\u0627\u062f \u067e\u0631 \u0631\u062a\u0628\u06c1 \u062f\u06cc\u0627 \u06c1\u06d2\u06d4 \u0646\u06cc\u0686\u06d2 \u06c1\u0631 \u0644\u0633\u0679\u0646\u06af \u06a9\u06cc \u0642\u06cc\u0645\u062a \u0627\u0648\u0631 \u0631\u06cc\u0679\u0646\u06af \u06a9\u0627 \u0645\u0648\u0627\u0632\u0646\u06c1 \u06a9\u0631\u06cc\u06ba\u06d4",
    "roman_urdu": "Mujhe aapki zaroorat ke mutabiq available options mile hain. Maine fit aur trust ko dekh kar rank kiya hai; neeche har listing ki price aur rating compare karein.",
    "pa": "Tuhadi lorh naal mildiyan stock vich maujood cheezan labh gayian. Fit te trust de mutabiq tarteeb ditti hai; hethaan price te rating compare karo.",
    "ps": "\u0645\u0627 \u062f \u062a\u0627\u0633\u0648 \u0644\u067e\u0627\u0631\u0647 \u0645\u0648\u062c\u0648\u062f \u0645\u0637\u0627\u0628\u0642 \u0644\u06cc\u0633\u062a\u0648\u0646\u0647 \u0648\u0645\u0648\u0646\u062f\u0644. \u062f \u0645\u0646\u0627\u0633\u0628\u062a \u0627\u0648 \u0627\u0639\u062a\u0645\u0627\u062f \u0644\u0647 \u0645\u062e\u06d0 \u0645\u06d0 \u0631\u062a\u0628\u0647 \u06a9\u0693\u064a; \u0642\u06cc\u0645\u062a \u0627\u0648 \u0631\u06cc\u0679\u0646\u06af \u06cc\u06d0 \u0645\u0648\u0627\u0632\u0646\u0647 \u06a9\u0693\u0626.",
    "sd": "Tawhan je lae stock mein milanda-julanda product milya aahin. Fit ain trust mutabiq tarteeb diti aahe; heth price ain rating jo muqablo kayo.",
    "fa": "\u0686\u0646\u062f \u06af\u0632\u06cc\u0646\u0647\u200c\u06cc \u0645\u0648\u062c\u0648\u062f \u0645\u0646\u0627\u0633\u0628 \u067e\u06cc\u062f\u0627 \u06a9\u0631\u062f\u0645. \u0622\u0646\u200c\u0647\u0627 \u0628\u0631 \u0627\u0633\u0627\u0633 \u0645\u0646\u0627\u0633\u0628\u062a \u0648 \u0627\u0639\u062a\u0645\u0627\u062f \u0631\u062a\u0628\u0647\u200c\u0628\u0646\u062f\u06cc \u0634\u062f\u0647\u200c\u0627\u0646\u062f\u061b \u0642\u06cc\u0645\u062a \u0648 \u0627\u0645\u062a\u06cc\u0627\u0632 \u0645\u0634\u062a\u0631\u06cc\u0627\u0646 \u0631\u0627 \u0645\u0642\u0627\u06cc\u0633\u0647 \u06a9\u0646\u06cc\u062f.",
    "zh": "\u627e\u5230\u4e86\u7b26\u5408\u9700\u6c42\u4e14\u6709\u5e93\u5b58\u7684\u5546\u54c1\u3002\u6211\u6839\u636e\u5339\u914d\u5ea6\u548c\u4fe1\u8a89\u6392\u5e8f\uff0c\u8bf7\u6bd4\u8f83\u4e0b\u65b9\u6bcf\u4ef6\u5546\u54c1\u7684\u5f53\u524d\u4ef7\u683c\u548c\u8bc4\u5206\u3002",
    "ar": "\u0639\u062b\u0631\u062a \u0639\u0644\u0649 \u062e\u064a\u0627\u0631\u0627\u062a \u0645\u062a\u0648\u0641\u0631\u0629 \u062a\u0646\u0627\u0633\u0628 \u0627\u062d\u062a\u064a\u0627\u062c\u0643. \u0631\u062a\u0628\u062a\u0647\u0627 \u062d\u0633\u0628 \u0627\u0644\u0645\u0644\u0627\u0621\u0645\u0629 \u0648\u0627\u0644\u062b\u0642\u0629\u061b \u0642\u0627\u0631\u0646 \u0627\u0644\u0633\u0639\u0631 \u0648\u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0644\u0643\u0644 \u0642\u0627\u0626\u0645\u0629 \u0623\u062f\u0646\u0627\u0647.",
}


def product_matches_response(locale: str | None) -> str:
    from app.services.localization import normalize_locale

    return _PRODUCT_MATCH_REPLIES.get(normalize_locale(locale), _PRODUCT_MATCH_REPLIES["en"])


def normalize_regional_text(text: str) -> str:
    """Map known Punjabi, Pashto, and Sindhi retail vocabulary to search terms."""
    text = normalize_multilingual_text(text)
    return re.sub(
        r"(?<![a-z0-9])[a-z][a-z0-9]*(?![a-z0-9])",
        lambda match: _REGIONAL_ALIASES.get(match.group(0), match.group(0)),
        text.lower(),
    )


def parse_regional_intent(text: str) -> dict[str, object]:
    """Expose detected regional vocabulary, style and negotiation intent without actions."""
    original_words = set(re.findall(r"[a-z0-9]+", text.lower()))
    dialect = next((name for name, markers in _DIALECT_MARKERS.items() if original_words & markers), None)
    normalized = normalize_shopping_text(text)
    shopping = parse_shopping_intent(text)
    style = next((item for item in ("wedding", "festive", "formal", "casual", "traditional") if item in normalized), None)
    negotiation_requested = bool(re.search(
        r"\b(?:discount|negotiate|cheaper|cheap|best price|lower price|sasta|sasto|"
        r"(?:rate|price)\s+(?:kam|discount|ghata[a-z]*))\b|"
        r"\b(?:kam|discount|ghata[a-z]*)\s+(?:rate|price)\b",
        normalized,
    ) or re.search(
        r"\b(?:rate|qeemat|bhaao)\s+(?:kam|ghat[a-z]*|ghata[a-z]*|discount)|"
        r"(?:kam|ghat[a-z]*|ghata[a-z]*|discount)\s+(?:rate|qeemat|bhaao)\b",
        text.lower(),
    ))
    return {
        "dialect": dialect,
        "category": shopping.category,
        "color": shopping.color,
        "size": shopping.size,
        "budget_min": shopping.budget_min,
        "budget_max": shopping.budget_max,
        "style": style,
        "negotiation_requested": negotiation_requested,
        "normalized_query": normalized,
        "advisory_only": True,
    }


def _amount(value: str, unit: str | None) -> float:
    amount = float(value.replace(",", ""))
    if unit in {"k", "thousand"}:
        amount *= 1_000
    elif unit in {"lac", "lakh"}:
        amount *= 100_000
    return amount


def _find_budget(text: str) -> tuple[float | None, float | None]:
    if re.search(r"\b(?:usd|dollars?|eur|gbp)\b", text):
        return None, None
    match = _RANGE.search(text)
    if match:
        captures = match.groups()
        first = _amount(captures[0], captures[1])
        second = _amount(captures[2], captures[3])
        return min(first, second), max(first, second)
    match = _BUDGET_VALUE.search(text)
    if match:
        values = match.groupdict()
        return None, _amount(values["amount"], values["unit"])
    match = _BUDGET_BOUND.search(text)
    if match:
        captures = match.groups()
        if captures[0] is not None:
            return None, _amount(captures[0], captures[1])
        return None, _amount(captures[2], captures[3])
    return None, None


def parse_shopping_intent(text: str, locale: str | None = None) -> ShoppingIntent:
    normalized = normalize_shopping_text(text, locale)
    categories = {
        label for aliases, label in _CATEGORIES
        if any(re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", normalized) for alias in aliases)
    }
    category = next(iter(categories)) if len(categories) == 1 else None
    colors = {
        value for alias, value in _COLORS.items()
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", normalized)
    }
    color = next(iter(colors)) if len(colors) == 1 else None

    size_pattern = r"\bsize\s+(extra small|x small|small|medium|med|large|extra large|x large|xs|xl|xxl|2xl|s|m|l)\b"
    size_matches = re.findall(size_pattern, normalized)
    if size_matches:
        sizes = {
            _SIZES.get(value) or {"s": "S", "m": "M", "l": "L"}.get(value)
            for value in size_matches
        }
        sizes.discard(None)
        size = next(iter(sizes)) if len(sizes) == 1 else None
    else:
        sizes = {
            value for alias, value in _SIZES.items()
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", normalized)
        }
        size = next(iter(sizes)) if len(sizes) == 1 else None

    budget_min, budget_max = _find_budget(normalized)
    return ShoppingIntent(category, color, size, budget_min, budget_max, normalized)


def extract_explicit_preferences(text: str) -> dict[str, object]:
    """Return only normalized fields from an explicit preference statement."""
    normalized = normalize_shopping_text(text)
    explicit = any(cue in normalized for cue in (
        "i prefer", "i like", "my favorite", "my favourite", "my usual", "i usually",
        "mera favorite", "meri favorite", "mujhe pasand", "pasand hai", "mera size",
        "meri size", "my budget", "mera budget", "my usual budget",
    ))
    if not explicit:
        return {}
    intent = parse_shopping_intent(text)
    result: dict[str, object] = {}
    if intent.size:
        result["clothing_size"] = intent.size
    if intent.color:
        result["favorite_color"] = intent.color
    if intent.budget_min is not None:
        result["budget_min"] = intent.budget_min
    if intent.budget_max is not None:
        result["budget_max"] = intent.budget_max
    preferences = [term for term in _SAFE_PREFERENCE_TERMS if term in normalized]
    if preferences:
        result["shopping_preferences"] = preferences
    if intent.category:
        result["preferred_category"] = intent.category
    return result


def intent_as_dict(intent: ShoppingIntent) -> dict[str, object]:
    return intent.public_constraints() | {"normalized_query": intent.normalized_query}

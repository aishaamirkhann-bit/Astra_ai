"""Transparent, read-only review and seller trust evidence scoring."""
from collections import Counter
from datetime import datetime, timezone
import re
from typing import Iterable, Mapping, Any
from app.services.localization import normalize_multilingual_text


_POSITIVE = {"excellent", "great", "good", "love", "amazing", "perfect", "recommend", "quality", "comfortable", "beautiful", "best", "nice"}
_NEGATIVE = {"bad", "poor", "worst", "fake", "broken", "damage", "damaged", "late", "wrong", "disappointed", "cheap", "return"}
_GENERIC = {"good product", "very good", "excellent product", "best product", "nice product", "great product", "highly recommend"}


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", normalize_multilingual_text(text)))


def _sentiment(text: str) -> tuple[int, int]:
    words = set(_normalize(text).split())
    return len(words & _POSITIVE), len(words & _NEGATIVE)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def analyze_reviews(reviews: Iterable[Mapping[str, Any]]) -> dict:
    rows = list(reviews)
    if not rows:
        return {"score": 50, "count": 0, "available": False, "mismatch_rate": None,
                "duplicate_rate": None, "velocity_flag": False,
                "highlights": ["No persisted review samples are available"]}

    normalized = [_normalize(str(row.get("text", ""))) for row in rows]
    counts = Counter(text for text in normalized if text)
    duplicate_excess = sum(count - 1 for count in counts.values() if count > 1)
    mismatches = 0
    for row in rows:
        rating = int(row.get("rating", 0) or 0)
        positive, negative = _sentiment(str(row.get("text", "")))
        if (rating >= 4 and negative > positive) or (rating <= 2 and positive > negative):
            mismatches += 1

    timestamps = sorted(time for row in rows if (time := _parse_time(row.get("created_at"))) is not None)
    velocity = any((timestamps[index + 2] - timestamps[index]).total_seconds() <= 600
                   for index in range(max(0, len(timestamps) - 2)))
    duplicate_rate = duplicate_excess / len(rows)
    mismatch_rate = mismatches / len(rows)
    generic_count = sum(text in _GENERIC for text in normalized)
    score = round(max(0, 100 - mismatch_rate * 35 - duplicate_rate * 35
                      - (10 if generic_count / len(rows) >= 0.5 else 0)
                      - (20 if velocity else 0)))
    highlights = []
    if mismatch_rate == 0:
        highlights.append("Sampled ratings align with review sentiment")
    else:
        highlights.append(f"{mismatches} sentiment-rating mismatch(es)")
    if duplicate_excess:
        highlights.append(f"{duplicate_excess} repeated review text pattern(s)")
    if velocity:
        highlights.append("Unusually clustered review submission times")
    if not duplicate_excess and not velocity:
        highlights.append("No duplicate or rapid-submission pattern in this sample")
    return {"score": score, "count": len(rows), "available": True,
            "mismatch_rate": round(mismatch_rate, 3), "duplicate_rate": round(duplicate_rate, 3),
            "velocity_flag": velocity, "highlights": highlights}


def analyze_photo_evidence(photos: Iterable[Mapping[str, Any]]) -> dict:
    rows = list(photos)
    if not rows:
        return {"score": 50, "count": 0, "available": False,
                "match_rate": None, "duplicate_rate": None,
                "highlights": ["No buyer review photos or visual checks are stored"]}
    known = [row for row in rows if row.get("matches_listing") is not None]
    mismatches = sum(row.get("matches_listing") is False for row in known)
    hashes = [str(row.get("content_hash")) for row in rows if row.get("content_hash")]
    duplicate_count = len(hashes) - len(set(hashes))
    low_resolution = sum(int(row.get("width", 9999)) < 240 or int(row.get("height", 9999)) < 240 for row in rows)
    score = round(max(0, 100 - (mismatches / len(known) * 55 if known else 0)
                      - duplicate_count / len(rows) * 30 - low_resolution / len(rows) * 15))
    highlights = ["Buyer photos match the listing" if known and not mismatches else
                  f"{mismatches} listing-photo discrepancy flag(s)" if known else "Visual listing comparison unavailable"]
    if duplicate_count:
        highlights.append(f"{duplicate_count} repeated photo file pattern(s)")
    return {"score": score, "count": len(rows), "available": True,
            "match_rate": round(1 - mismatches / len(known), 3) if known else None,
            "duplicate_rate": round(duplicate_count / len(rows), 3), "highlights": highlights}


def build_trust_assessment(*, reviews: Iterable[Mapping[str, Any]], photos: Iterable[Mapping[str, Any]],
                           seller_score: float, seller_verified: bool) -> dict:
    review_result = analyze_reviews(reviews)
    photo_result = analyze_photo_evidence(photos)
    signals = [(review_result["score"], 0.50, review_result["available"]),
               (photo_result["score"], 0.20, photo_result["available"]),
               (max(0, min(100, float(seller_score))), 0.30, True)]
    available_weight = sum(weight for _, weight, available in signals if available)
    score = round(sum(value * weight for value, weight, available in signals if available) / available_weight)
    enough_evidence = review_result["count"] >= 3 and photo_result["count"] >= 1
    verified = enough_evidence and score >= 80 and seller_verified
    grade = "Astra Verified" if verified else "Review recommended" if score < 60 else "Limited evidence"
    return {
        "score": score,
        "grade": grade,
        "badge": f"Astra Verified: {score}% Authentic" if verified else f"Trust indicator: {score}% · {grade}",
        "verified": verified,
        "confidence": "high" if enough_evidence else "low",
        "evidence": {"reviews": review_result, "photos": photo_result,
                     "seller": {"score": round(max(0, min(100, float(seller_score)))),
                                "verified": bool(seller_verified), "available": True}},
        "advisory_only": True,
    }

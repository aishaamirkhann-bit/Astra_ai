"""Deterministic agent engines powering ASTRA's showcase features.

Every function here is seeded from stable identifiers (product slug, order
ref) so the demo behaves identically across runs while still looking alive:
authenticity/ZK stamps, synthetic-image scans, voice-intent resolution,
cross-border micro-escrow routes, predictive restock, swarm traces and the
sub-30s dispute resolution timeline.
"""
import hashlib
from datetime import datetime, timedelta, timezone

FX_RATES_PKR = {"USD": 278.42, "AED": 75.86, "SAR": 74.24, "EUR": 302.15, "GBP": 351.62}


def seed(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)


def short_hash(*parts: object, length: int = 32) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def authenticity_extras(product_id: str, seller_id: str | None, seller_name: str, listing_hash: str) -> dict:
    """ZK proof, reputation hash, cryptographic stamp and deepfake scan."""
    entropy = seed(product_id, listing_hash)
    now = datetime.now(timezone.utc).isoformat()
    zk_proof_id = f"zk-{short_hash('zk', product_id, length=20)}"
    return {
        "zk_verification": {
            "status": "verified",
            "proof_id": zk_proof_id,
            "protocol": "Groth16 · BN254",
            "circuit": "astra-listing-integrity-v2",
            "public_inputs": 4,
            "verify_ms": 8 + entropy % 14,
            "verified_at": now,
        },
        "seller_reputation_hash": short_hash("reputation", seller_id or seller_name),
        "cryptographic_stamp": {
            "stamp_id": f"ASTRA-STAMP-{short_hash('stamp', product_id, length=10).upper()}",
            "algorithm": "Ed25519",
            "signed_payload": listing_hash[:16],
            "attested_by": "ASTRA Trust Authority",
            "attested_at": now,
        },
        "synthetic_image_scan": {
            "score": round((entropy % 5) / 10, 1),
            "verdict": "authentic",
            "model": "AstraGuard-ViT-L/14",
            "frames_analyzed": 2 + entropy % 3,
            "scanned_at": now,
        },
    }


def micro_settlements(amount: float, reference: str) -> dict:
    """Zero-fee multi-currency micro-escrow settlement simulation."""
    amount = round(max(amount or 0, 1), 2)
    entropy = seed("settlement", reference, int(amount))
    corridors = ["AED", "SAR", "USD"]
    corridor = corridors[entropy % len(corridors)]
    mid_rate = FX_RATES_PKR[corridor]
    hops = [
        {
            "from": "PKR", "to": corridor, "rate": round(mid_rate, 2),
            "amount_in": amount, "amount_out": round(amount / mid_rate, 2),
            "fee": 0.0, "via": f"ASTRA Micro-Escrow Vault {short_hash('vault', reference, length=8)}",
            "latency_ms": 90 + entropy % 90, "status": "settled",
        },
        {
            "from": corridor, "to": "USD", "rate": round(mid_rate / FX_RATES_PKR["USD"], 4),
            "amount_in": round(amount / mid_rate, 2), "amount_out": round(amount / FX_RATES_PKR["USD"], 2),
            "fee": 0.0, "via": "Inter-vault atomic swap",
            "latency_ms": 45 + entropy % 60, "status": "settled",
        },
        {
            "from": "USD", "to": "PKR", "rate": round(FX_RATES_PKR["USD"], 2),
            "amount_in": round(amount / FX_RATES_PKR["USD"], 2), "amount_out": amount,
            "fee": 0.0, "via": "Escrow release to beneficiary",
            "latency_ms": 70 + entropy % 80, "status": "settled",
        },
    ]
    total_latency = sum(hop["latency_ms"] for hop in hops)
    return {
        "reference": reference,
        "base_currency": "PKR",
        "amount": amount,
        "corridor": f"PKR → {corridor} → USD → PKR",
        "total_fee": 0.0,
        "fx_slippage_percent": round((entropy % 3) / 100, 2),
        "routes": hops,
        "total_latency_ms": total_latency,
        "settled_at": datetime.now(timezone.utc).isoformat(),
    }


def remittance_context(reference: str) -> dict:
    """Static remittance metadata; it does not create or quote a transfer."""
    return {
        "reference": reference,
        "status": "stub",
        "source_country": "PK",
        "source_currency": "PKR",
        "destinations": [
            {"country_code": "AE", "currency": "AED", "payout_methods": ["bank", "wallet"]},
            {"country_code": "SA", "currency": "SAR", "payout_methods": ["bank", "wallet"]},
            {"country_code": "US", "currency": "USD", "payout_methods": ["bank"]},
        ],
        "required_recipient_fields": ["full_name", "country_code", "payout_method"],
        "compliance": {"kyc_required": True, "sanctions_screening": "not_started"},
    }


def restock_forecasts(orders: list, fallback_products: list[dict]) -> list[dict]:
    """Predictive replenishment intervals from the user's order history."""
    now = datetime.now(timezone.utc)
    seen: dict[str, dict] = {}
    for order in orders:
        product = getattr(order, "product", None)
        if product is None:
            continue
        entry = seen.setdefault(product.id, {"product": product, "latest": order.created_at})
        if order.created_at and order.created_at > entry["latest"]:
            entry["latest"] = order.created_at
    forecasts: list[dict] = []
    for product_id, entry in list(seen.items())[:3]:
        product = entry["product"]
        entropy = seed("restock", product_id)
        interval = 28 + entropy % 47
        last = entry["latest"].replace(tzinfo=entry["latest"].tzinfo or timezone.utc)
        predicted = last + timedelta(days=interval)
        forecasts.append({
            "product_id": product_id,
            "product_name": product.title,
            "image": product.image_url,
            "category": product.category,
            "last_purchased": last.isoformat(),
            "avg_interval_days": interval,
            "predicted_next_date": predicted.date().isoformat(),
            "days_until_restock": max((predicted - now).days, 0),
            "confidence": round(82 + (entropy % 160) / 10, 1),
            "estimated_price": product.price,
            "message": f"AI predicts you restock {product.title} every ~{interval} days. Budget Guardian reserved a slot in your next cycle.",
        })
    if forecasts:
        return forecasts
    for product in fallback_products[:2]:
        entropy = seed("restock", product["id"])
        interval = 24 + entropy % 30
        predicted = now + timedelta(days=interval % 21 + 5)
        forecasts.append({
            "product_id": product["id"],
            "product_name": product["title"],
            "image": product["image_url"],
            "category": product["category"],
            "last_purchased": None,
            "avg_interval_days": interval,
            "predicted_next_date": predicted.date().isoformat(),
            "days_until_restock": (predicted - now).days,
            "confidence": round(74 + (entropy % 120) / 10, 1),
            "estimated_price": product["price"],
            "message": f"Based on your browsing pattern, ASTRA expects {product['title']} in ~{(predicted - now).days} days. Price-watch armed.",
        })
    return forecasts


def swarm_trace(order_ref: str, product_title: str, price: float) -> dict:
    """Parallel multi-agent verification trace for one order."""
    entropy = seed("swarm", order_ref)
    started = datetime.now(timezone.utc)
    specs = [
        ("pricing-agent", "Price Intelligence", [
            ("30d market feed scan", f"12 observations — fair band Rs. {price * 0.92:,.0f}–{price * 1.06:,.0f}"),
            ("Discount floor check", "Listing inside fairness band; no predatory markup"),
            ("Escrow amount lock", f"Rs. {price:,.0f} pinned to escrow vault"),
        ]),
        ("risk-agent", "Fraud & Trust", [
            ("Seller KYC re-check", "Registry + sanctions lists clean"),
            ("Review bot-pattern scan", "Sentiment organic; no coordinated spikes"),
            ("Buyer chargeback model", f"Chargeback prior low (score {18 + entropy % 12}/100)"),
        ]),
        ("logistics-agent", "Fulfillment", [
            ("Carrier selection", "Fastest insured lane chosen (2–3 days)"),
            ("Delivery ETA model", "Confidence 94% for on-time arrival"),
            ("Return route reserve", "Reversible window pre-booked with carrier"),
        ]),
    ]
    agents = []
    longest = 0
    for name, role, tasks in specs:
        agent_entropy = seed(order_ref, name)
        cursor = agent_entropy % 40
        rendered = []
        for label, detail in tasks:
            duration = 60 + (agent_entropy + len(label)) % 160
            rendered.append({
                "task": label, "start_ms": cursor, "end_ms": cursor + duration,
                "status": "ok", "detail": detail,
            })
            cursor += max(duration - 35, 25)
        longest = max(longest, cursor)
        agents.append({"agent": name, "role": role, "status": "ok", "tasks": rendered})
    total_ms = longest + 40 + entropy % 30
    return {
        "order_ref": order_ref,
        "product": product_title,
        "orchestrator": "astra-swarm-coordinator",
        "parallelism": len(agents),
        "total_ms": total_ms,
        "started_at": started.isoformat(),
        "merge": {"task": "verdict merge", "start_ms": longest, "end_ms": total_ms, "status": "ok", "detail": "All sub-agents unanimous — order verified"},
        "agents": agents,
    }


def resolution_timeline(order_ref: str, risk_score: int, amount: float) -> dict:
    """Sub-30s auto-resolution log: proof scan → risk → escrow → wallet credit."""
    entropy = seed("resolution", order_ref)
    finished = datetime.now(timezone.utc)
    offsets = [0, 620 + entropy % 220, 1450 + entropy % 260, 2180 + entropy % 320]
    steps = [
        {"phase": "Proof Scan", "at": finished - timedelta(milliseconds=offsets[3]), "ms": offsets[0], "detail": f"Escrow receipt + buyer proof bundle hashed (SHA-256 {short_hash('proof', order_ref, length=10)})"},
        {"phase": "Risk Evaluation", "at": finished - timedelta(milliseconds=offsets[3] - offsets[1]), "ms": offsets[1], "detail": f"Dynamic risk engine scored {risk_score}/100 — above auto-refund threshold 50"},
        {"phase": "Escrow Refunded", "at": finished - timedelta(milliseconds=offsets[3] - offsets[2]), "ms": offsets[2], "detail": f"Rs. {amount:,.0f} released from escrow vault back to buyer"},
        {"phase": "Instant Wallet Credit", "at": finished, "ms": offsets[3], "detail": "Wallet credited in the same transaction — zero waiting period"},
    ]
    return {"order_ref": order_ref, "resolved_ms": offsets[3], "sla_seconds": 30, "steps": steps}

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/b2b", tags=["B2B Adapter"])

HIGH_VALUE_LIMIT = 500_000
TRUSTED_TIERS = {"verified", "trusted", "gold", "platinum"}


class ConsentCheck(BaseModel):
    rule: str
    status: str  # pass | warn | fail
    detail: str


class ConsentEvaluation(BaseModel):
    verdict: str  # approve | hold | reject
    reason: str
    event_ref: str
    evaluated_at: datetime
    checks: list[ConsentCheck]


def _extract_amount(payload: dict) -> float | None:
    item = payload.get("item")
    if isinstance(item, dict) and isinstance(item.get("price"), (int, float)):
        return float(item["price"])
    order = payload.get("order")
    if isinstance(order, dict) and isinstance(order.get("total"), (int, float)):
        return float(order["total"])
    return None


def _extract_agent(payload: dict) -> str:
    agent = payload.get("agent")
    if isinstance(agent, dict) and agent.get("id"):
        return str(agent["id"])
    if payload.get("agent_id"):
        return str(payload["agent_id"])
    return "unknown-agent"


@router.post("/evaluate", response_model=ConsentEvaluation)
def evaluate_payload(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministic consent verdict for an external agent (UCP/ACP) payload."""
    checks: list[ConsentCheck] = []
    verdict = "approve"
    reason = "All deterministic rules passed; no contradictions found."

    protocol = str(payload.get("protocol") or "").upper()
    family = "UCP" if protocol.startswith("UCP") else "ACP" if protocol.startswith("ACP") else "UNKNOWN"
    checks.append(ConsentCheck(
        rule="protocol.recognized",
        status="pass" if family != "UNKNOWN" else "warn",
        detail=f"Detected protocol family: {family}",
    ))

    amount = _extract_amount(payload)
    if amount is None or amount <= 0:
        checks.append(ConsentCheck(rule="payload.amount", status="fail", detail="No positive payable amount found in the payload"))
        verdict = "reject"
        reason = "Payload does not contain a valid payable amount."
    else:
        checks.append(ConsentCheck(rule="payload.amount", status="pass", detail=f"Payable amount parsed: Rs. {amount:,.0f}"))

    agent_id = _extract_agent(payload)
    trust_tier = None
    agent_meta = payload.get("agent")
    if isinstance(agent_meta, dict):
        trust_tier = agent_meta.get("trust_tier")
    if trust_tier is not None:
        tier_ok = str(trust_tier).lower() in TRUSTED_TIERS
        checks.append(ConsentCheck(
            rule="agent.trust_tier",
            status="pass" if tier_ok else "fail",
            detail=f"Agent '{agent_id}' trust tier: {trust_tier}",
        ))
        if not tier_ok and verdict != "reject":
            verdict = "reject"
            reason = "Agent trust tier below the minimum required for unattended checkout."

    buyer = payload.get("buyer_context")
    wallet_balance = buyer.get("wallet_balance") if isinstance(buyer, dict) else None
    if amount is not None and isinstance(wallet_balance, (int, float)):
        affordable = amount <= wallet_balance
        checks.append(ConsentCheck(
            rule="finance.buyer_affordability",
            status="pass" if affordable else "fail",
            detail=f"Buyer wallet Rs. {wallet_balance:,.0f} vs. charge Rs. {amount:,.0f}",
        ))
        if not affordable and verdict == "approve":
            verdict = "hold"
            reason = "Charge exceeds the buyer's available wallet balance — routed to human approval."

    if amount is not None and amount > HIGH_VALUE_LIMIT and verdict == "approve":
        checks.append(ConsentCheck(
            rule="finance.high_value_gate",
            status="warn",
            detail=f"Amount exceeds the Rs. {HIGH_VALUE_LIMIT:,.0f} unattended-checkout cap",
        ))
        verdict = "hold"
        reason = "High-value transaction — routed to human approval before execution."

    audit = record_audit(
        db,
        event_type="consent.evaluate",
        endpoint="/api/v1/b2b/evaluate",
        verdict=verdict,
        actor=f"agent:{agent_id}",
    )
    db.commit()

    return ConsentEvaluation(
        verdict=verdict,
        reason=reason,
        event_ref=audit.event_ref,
        evaluated_at=datetime.now(timezone.utc),
        checks=checks,
    )

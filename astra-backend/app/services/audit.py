import secrets

from sqlalchemy.orm import Session

from app.models.pipeline import AuditLog


def record_audit(
    db: Session,
    *,
    event_type: str,
    endpoint: str,
    verdict: str,
    actor: str,
) -> AuditLog:
    """Append an immutable audit entry; safe to call before the caller's commit."""
    existing = {ref for (ref,) in db.query(AuditLog.event_ref).all()}
    while True:
        event_ref = f"EVT-{secrets.randbelow(1_000_000):06d}"
        if event_ref not in existing:
            break
    entry = AuditLog(
        event_ref=event_ref,
        event_type=event_type,
        endpoint=endpoint,
        verdict=verdict,
        actor=actor,
    )
    db.add(entry)
    db.flush()
    return entry

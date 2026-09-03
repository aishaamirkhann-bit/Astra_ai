from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.budget import BudgetAlert
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _feed(db: Session, user_id: int) -> list[NotificationOut]:
    items = [NotificationOut(id=f"notification-{item.id}", category="order_update", title="Order update", message=item.message, is_read=bool(item.is_read), created_at=item.created_at.replace(tzinfo=item.created_at.tzinfo or timezone.utc), href="/orders") for item in db.query(Notification).filter(Notification.user_id == user_id).all()]
    for alert in db.query(BudgetAlert).filter(BudgetAlert.user_id == user_id).all():
        category = "deal_match" if alert.alert_type == "Deal_Matched" else "financial_alert"
        title = "AI deal match" if category == "deal_match" else "Financial alert"
        href = f"/deals?deal={alert.deal_id}&goal={alert.goal_id}" if alert.deal_id else "/goals"
        items.append(NotificationOut(id=f"budget-{alert.alert_id}", category=category, title=title, message=alert.message, is_read=bool(alert.is_read), created_at=alert.created_at.replace(tzinfo=alert.created_at.tzinfo or timezone.utc), href=href, deal_id=alert.deal_id, goal_id=alert.goal_id))
    return sorted(items, key=lambda item: item.created_at, reverse=True)


@router.get("", response_model=NotificationListOut)
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = _feed(db, current_user.id)
    return NotificationListOut(items=items, unread_count=sum(not item.is_read for item in items))


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"unread_count": sum(not item.is_read for item in _feed(db, current_user.id))}


@router.post("/{notification_id}/read", status_code=204)
def mark_read(notification_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if notification_id.startswith("notification-"):
        row = db.query(Notification).filter(Notification.id == int(notification_id.removeprefix("notification-")), Notification.user_id == current_user.id).first()
    elif notification_id.startswith("budget-"):
        row = db.query(BudgetAlert).filter(BudgetAlert.alert_id == notification_id.removeprefix("budget-"), BudgetAlert.user_id == current_user.id).first()
    else: row = None
    if not row: raise HTTPException(status_code=404, detail="Notification not found")
    row.is_read = True; db.commit(); return Response(status_code=204)


@router.delete("", status_code=204)
def clear_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == current_user.id).delete()
    db.query(BudgetAlert).filter(BudgetAlert.user_id == current_user.id).delete()
    db.commit(); return Response(status_code=204)

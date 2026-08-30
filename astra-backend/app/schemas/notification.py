from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    category: Literal["deal_match", "order_update", "financial_alert"]
    title: str
    message: str
    is_read: bool
    created_at: datetime
    href: str | None = None
    deal_id: str | None = None
    goal_id: int | None = None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int

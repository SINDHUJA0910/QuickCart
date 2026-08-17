"""Schemas for the notification feed (retailer + customer)."""
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    title: str
    body: str | None
    category: str
    related_id: str | None
    read: bool
    created_at: datetime

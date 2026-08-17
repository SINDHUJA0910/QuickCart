"""Schemas for shopping session lifecycle."""
from datetime import datetime

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    store_id: str


class SessionResponse(BaseModel):
    id: str
    store_id: str
    store_name: str
    status: str
    payment_status: str
    exit_status: str
    entry_time: datetime
    checkout_time: datetime | None

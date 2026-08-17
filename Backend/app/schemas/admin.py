"""Schemas for the (optional) admin view — platform-wide, cross-retailer."""
from pydantic import BaseModel


class PlatformStatsResponse(BaseModel):
    total_stores: int
    total_retailers: int
    total_customers: int
    total_sessions: int
    total_revenue_paise: int
    open_ai_alerts: int


class AdminStoreSummary(BaseModel):
    id: str
    name: str
    store_type: str
    is_active: bool
    retailer_id: str


class SystemHealthResponse(BaseModel):
    status: str
    database_reachable: bool

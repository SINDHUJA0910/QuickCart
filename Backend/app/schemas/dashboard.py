"""Schemas for the retailer dashboard: live stats, sessions, reports."""
from datetime import datetime

from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    todays_sales_paise: int
    monthly_sales_paise: int
    total_products: int
    low_stock_products: int
    customers_inside_store: int
    live_sessions: int
    pending_payments: int
    open_ai_alerts: int


class LiveSessionResponse(BaseModel):
    session_id: str
    customer_name: str
    entry_time: datetime
    items_scanned: int
    payment_status: str
    exit_status: str
    duration_minutes: float


class RecentTransactionResponse(BaseModel):
    session_id: str
    customer_name: str
    invoice_number: str | None
    total_paise: int
    payment_status: str
    checkout_time: datetime | None


class TopProductStat(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    revenue_paise: int


class PeakHourStat(BaseModel):
    hour: int  # 0-23
    session_count: int

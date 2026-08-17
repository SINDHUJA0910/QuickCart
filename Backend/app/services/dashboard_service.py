"""
Dashboard live statistics.

Every number here is computed directly from current table state at request
time (e.g. `count(sessions where status='active')` for "customers inside
store") rather than maintained as a running counter that could drift out of
sync with reality — correctness matters more than the marginal query cost
at the scale a single supermarket dashboard operates at.
"""
from datetime import datetime, timezone

from app.db.supabase_client import get_service_client
from app.schemas.dashboard import DashboardStatsResponse, LiveSessionResponse, RecentTransactionResponse
from app.services.store_ownership import verify_store_ownership


def get_dashboard_stats(store_id: str, retailer_id: str) -> DashboardStatsResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sessions = service.table("shopping_sessions").select("*").eq("store_id", store_id).execute()
    session_rows = sessions.data or []

    invoices = service.table("invoices").select("*, shopping_sessions(store_id)").execute()
    store_invoices = [
        inv for inv in (invoices.data or [])
        if (inv.get("shopping_sessions") or {}).get("store_id") == store_id
    ]

    def _paid_since(cutoff: datetime) -> int:
        total = 0
        for inv in store_invoices:
            created_at = inv.get("created_at")
            if created_at and _parse_dt(created_at) >= cutoff:
                total += inv["total_paise"]
        return total

    products = service.table("products").select("*").eq("store_id", store_id).eq("is_active", True).execute()
    product_rows = products.data or []

    alerts = service.table("ai_alerts").select("id").eq("store_id", store_id).eq("status", "open").execute()

    return DashboardStatsResponse(
        todays_sales_paise=_paid_since(today_start),
        monthly_sales_paise=_paid_since(month_start),
        total_products=len(product_rows),
        low_stock_products=sum(1 for p in product_rows if p["stock_quantity"] <= p["low_stock_threshold"]),
        customers_inside_store=sum(1 for s in session_rows if s["status"] == "active"),
        live_sessions=sum(1 for s in session_rows if s["status"] == "active"),
        pending_payments=sum(1 for s in session_rows if s["payment_status"] == "pending" and s["status"] == "active"),
        open_ai_alerts=len(alerts.data or []),
    )


def get_live_sessions(store_id: str, retailer_id: str) -> list[LiveSessionResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    sessions = (
        service.table("shopping_sessions")
        .select("*, customers(full_name)")
        .eq("store_id", store_id)
        .eq("status", "active")
        .execute()
    )

    now = datetime.now(timezone.utc)
    results = []
    for row in sessions.data or []:
        cart_items = (
            service.table("cart_items")
            .select("quantity")
            .eq("session_id", row["id"])
            .is_("removed_at", "null")
            .execute()
        )
        items_scanned = sum(i["quantity"] for i in (cart_items.data or []))
        entry_time = _parse_dt(row["entry_time"])
        duration = (now - entry_time).total_seconds() / 60

        customer = row.get("customers") or {}
        results.append(
            LiveSessionResponse(
                session_id=row["id"],
                customer_name=customer.get("full_name", "Unknown"),
                entry_time=entry_time,
                items_scanned=items_scanned,
                payment_status=row["payment_status"],
                exit_status=row["exit_status"],
                duration_minutes=round(duration, 1),
            )
        )
    return results


def get_recent_transactions(store_id: str, retailer_id: str, limit: int = 20) -> list[RecentTransactionResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    sessions = (
        service.table("shopping_sessions")
        .select("*, customers(full_name)")
        .eq("store_id", store_id)
        .eq("payment_status", "success")
        .execute()
    )

    results = []
    for row in sessions.data or []:
        invoice = service.table("invoices").select("*").eq("session_id", row["id"]).execute()
        inv = invoice.data[0] if invoice.data else None
        customer = row.get("customers") or {}
        results.append(
            RecentTransactionResponse(
                session_id=row["id"],
                customer_name=customer.get("full_name", "Unknown"),
                invoice_number=inv["invoice_number"] if inv else None,
                total_paise=inv["total_paise"] if inv else 0,
                payment_status=row["payment_status"],
                checkout_time=_parse_dt(row["checkout_time"]) if row.get("checkout_time") else None,
            )
        )

    results.sort(key=lambda r: r.checkout_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return results[:limit]


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

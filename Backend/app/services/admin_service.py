"""Platform-wide admin views: cross-retailer stats, store listing, system health."""
from app.db.supabase_client import get_service_client
from app.schemas.admin import AdminStoreSummary, PlatformStatsResponse, SystemHealthResponse


def get_platform_stats() -> PlatformStatsResponse:
    service = get_service_client()

    stores = service.table("stores").select("id").execute()
    retailers = service.table("retailers").select("id").execute()
    customers = service.table("customers").select("id").execute()
    sessions = service.table("shopping_sessions").select("id").execute()
    invoices = service.table("invoices").select("total_paise").execute()
    open_alerts = service.table("ai_alerts").select("id").eq("status", "open").execute()

    total_revenue = sum(inv["total_paise"] for inv in (invoices.data or []))

    return PlatformStatsResponse(
        total_stores=len(stores.data or []),
        total_retailers=len(retailers.data or []),
        total_customers=len(customers.data or []),
        total_sessions=len(sessions.data or []),
        total_revenue_paise=total_revenue,
        open_ai_alerts=len(open_alerts.data or []),
    )


def list_all_stores() -> list[AdminStoreSummary]:
    service = get_service_client()
    result = service.table("stores").select("*").execute()
    return [
        AdminStoreSummary(
            id=row["id"], name=row["name"], store_type=row["store_type"],
            is_active=row["is_active"], retailer_id=row["retailer_id"],
        )
        for row in (result.data or [])
    ]


def check_system_health() -> SystemHealthResponse:
    service = get_service_client()
    try:
        service.table("stores").select("id").limit(1).execute()
        return SystemHealthResponse(status="ok", database_reachable=True)
    except Exception:
        return SystemHealthResponse(status="degraded", database_reachable=False)

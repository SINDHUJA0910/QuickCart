"""Sales reporting: CSV transaction export, top products, peak shopping hours."""
import csv
import io
from collections import defaultdict

from app.db.supabase_client import get_service_client
from app.schemas.dashboard import PeakHourStat, TopProductStat
from app.services.dashboard_service import _parse_dt
from app.services.store_ownership import verify_store_ownership


def export_transactions_csv(store_id: str, retailer_id: str) -> str:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    sessions = (
        service.table("shopping_sessions")
        .select("*, customers(full_name)")
        .eq("store_id", store_id)
        .eq("payment_status", "success")
        .execute()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Session ID", "Customer", "Invoice Number", "Total (INR)", "Checkout Time"])

    for row in sessions.data or []:
        invoice = service.table("invoices").select("*").eq("session_id", row["id"]).execute()
        inv = invoice.data[0] if invoice.data else None
        customer = row.get("customers") or {}
        writer.writerow(
            [
                row["id"],
                customer.get("full_name", ""),
                inv["invoice_number"] if inv else "",
                f"{(inv['total_paise'] if inv else 0) / 100:.2f}",
                row.get("checkout_time", ""),
            ]
        )

    return buffer.getvalue()


def get_top_products(store_id: str, retailer_id: str, limit: int = 10) -> list[TopProductStat]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    sessions = service.table("shopping_sessions").select("id").eq("store_id", store_id).execute()
    session_ids = {s["id"] for s in (sessions.data or [])}

    cart_items = service.table("cart_items").select("*, products(name)").is_("removed_at", "null").execute()

    stats: dict[str, dict] = defaultdict(lambda: {"name": "", "units": 0, "revenue": 0})
    for item in cart_items.data or []:
        if item["session_id"] not in session_ids:
            continue
        product = item.get("products") or {}
        entry = stats[item["product_id"]]
        entry["name"] = product.get("name", "")
        entry["units"] += item["quantity"]
        entry["revenue"] += item["unit_price_paise"] * item["quantity"]

    ranked = sorted(stats.items(), key=lambda kv: kv[1]["revenue"], reverse=True)[:limit]
    return [
        TopProductStat(product_id=pid, product_name=v["name"], units_sold=v["units"], revenue_paise=v["revenue"])
        for pid, v in ranked
    ]


def get_peak_hours(store_id: str, retailer_id: str) -> list[PeakHourStat]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    sessions = service.table("shopping_sessions").select("entry_time").eq("store_id", store_id).execute()

    counts: dict[int, int] = defaultdict(int)
    for row in sessions.data or []:
        hour = _parse_dt(row["entry_time"]).hour
        counts[hour] += 1

    return [PeakHourStat(hour=h, session_count=counts.get(h, 0)) for h in range(24) if counts.get(h, 0) > 0]

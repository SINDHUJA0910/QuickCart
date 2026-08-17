"""
Shopping session service.

The single most important invariant enforced here: a customer may have at
most one 'active' session at any time, across all stores. This is what makes
"customers inside store" counts on the retailer dashboard (Phase 5) and the
AI pipeline's per-customer tracking (Phase 6) meaningful — without it, a
customer could in principle open sessions at two stores simultaneously and
neither retailer's view of "who's currently shopping" would be trustworthy.

This is enforced here at the application level (query-then-insert) rather
than relying solely on a DB constraint, since "one active row per customer"
is a partial-uniqueness condition (unique only when status='active') that
needs a partial unique index to enforce in Postgres directly — noted in
Phase 8's hardening pass as an additional safety net to add at the DB layer;
the application-level check is the authoritative gate for now.
"""
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.session import SessionResponse


def get_active_session(customer_id: str) -> SessionResponse | None:
    service = get_service_client()
    result = (
        service.table("shopping_sessions")
        .select("*, stores(name)")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _to_response(result.data[0])


def create_session(customer_id: str, store_id: str) -> SessionResponse:
    service = get_service_client()

    if get_active_session(customer_id) is not None:
        raise ConflictError(
            "You already have an active shopping session. Finish or exit that session before starting another."
        )

    store = service.table("stores").select("id, name, is_active").eq("id", store_id).execute()
    if not store.data:
        raise NotFoundError("Store not found")
    if not store.data[0]["is_active"]:
        raise ConflictError("This store is not currently accepting shoppers")

    inserted = (
        service.table("shopping_sessions")
        .insert({"customer_id": customer_id, "store_id": store_id})
        .execute()
    )
    row = inserted.data[0]
    row["stores"] = {"name": store.data[0]["name"]}
    return _to_response(row)


def get_session_or_raise(session_id: str, customer_id: str) -> dict:
    """Fetches a raw session row and verifies it belongs to the requesting customer.
    Returns the raw dict (not the response schema) since cart_service needs
    fields like `status` that aren't part of the public SessionResponse shape."""
    service = get_service_client()
    result = service.table("shopping_sessions").select("*").eq("id", session_id).execute()
    if not result.data:
        raise NotFoundError("Shopping session not found")

    session = result.data[0]
    if session["customer_id"] != customer_id:
        raise ForbiddenError("This session does not belong to you")
    return session


def _to_response(row: dict) -> SessionResponse:
    store_name = row.get("stores", {}).get("name") if isinstance(row.get("stores"), dict) else None
    return SessionResponse(
        id=row["id"],
        store_id=row["store_id"],
        store_name=store_name or "",
        status=row["status"],
        payment_status=row["payment_status"],
        exit_status=row["exit_status"],
        entry_time=row["entry_time"],
        checkout_time=row.get("checkout_time"),
    )

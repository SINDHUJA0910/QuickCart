"""
Centralized store-ownership check.

Every retailer-scoped operation (inventory, live sessions, reports) needs to
answer the same question: "does this store belong to this retailer?" Rather
than re-implementing that lookup in every service (and risking one of them
forgetting it), all of them call this single function. If a store-scoping
bug ever exists, it exists in exactly one place to fix.
"""
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.supabase_client import get_service_client


def verify_store_ownership(store_id: str, retailer_id: str) -> dict:
    """Returns the store row if owned by this retailer, else raises."""
    service = get_service_client()
    result = service.table("stores").select("*").eq("id", store_id).execute()
    if not result.data:
        raise NotFoundError("Store not found")
    store = result.data[0]
    if store["retailer_id"] != retailer_id:
        raise ForbiddenError("This store does not belong to you")
    return store

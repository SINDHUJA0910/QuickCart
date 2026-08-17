"""Retailer-side store CRUD (as distinct from store_service.py, which is the
public customer-facing search)."""
from app.db.supabase_client import get_service_client
from app.schemas.store import RetailerStoreResponse, StoreCreateRequest, StoreUpdateRequest
from app.services.store_ownership import verify_store_ownership


def _to_response(row: dict) -> RetailerStoreResponse:
    return RetailerStoreResponse(
        id=row["id"],
        name=row["name"],
        store_type=row["store_type"],
        is_active=row["is_active"],
        address_line=row.get("address_line"),
        city=row.get("city"),
        rating=row.get("rating") or 0.0,
    )


def create_store(retailer_id: str, payload: StoreCreateRequest) -> RetailerStoreResponse:
    service = get_service_client()
    data = payload.model_dump()
    data["retailer_id"] = retailer_id
    result = service.table("stores").insert(data).execute()
    return _to_response(result.data[0])


def list_my_stores(retailer_id: str) -> list[RetailerStoreResponse]:
    service = get_service_client()
    result = service.table("stores").select("*").eq("retailer_id", retailer_id).execute()
    return [_to_response(row) for row in (result.data or [])]


def update_store(store_id: str, retailer_id: str, payload: StoreUpdateRequest) -> RetailerStoreResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if updates:
        service.table("stores").update(updates).eq("id", store_id).execute()

    result = service.table("stores").select("*").eq("id", store_id).execute()
    return _to_response(result.data[0])

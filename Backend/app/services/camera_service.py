"""Retailer CCTV camera CRUD, including shelf-zone ROI configuration."""
from app.core.exceptions import NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.camera import CameraCreateRequest, CameraResponse, CameraUpdateRequest, ZoneConfig
from app.services.store_ownership import verify_store_ownership


def _to_response(row: dict) -> CameraResponse:
    return CameraResponse(
        id=row["id"],
        label=row["label"],
        status=row["status"],
        stream_url=row["stream_url"],
        zone_config=[ZoneConfig(**z) for z in (row.get("zone_config") or [])],
    )


def create_camera(store_id: str, retailer_id: str, payload: CameraCreateRequest) -> CameraResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    data = {
        "store_id": store_id,
        "label": payload.label,
        "stream_url": payload.stream_url,
        "zone_config": [z.model_dump() for z in payload.zone_config],
    }
    result = service.table("cctv_cameras").insert(data).execute()
    return _to_response(result.data[0])


def list_cameras(store_id: str, retailer_id: str) -> list[CameraResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)
    result = service.table("cctv_cameras").select("*").eq("store_id", store_id).execute()
    return [_to_response(row) for row in (result.data or [])]


def update_camera(store_id: str, camera_id: str, retailer_id: str, payload: CameraUpdateRequest) -> CameraResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    existing = service.table("cctv_cameras").select("id").eq("id", camera_id).eq("store_id", store_id).execute()
    if not existing.data:
        raise NotFoundError("Camera not found in this store")

    updates = payload.model_dump(exclude_none=True)
    if "zone_config" in updates:
        updates["zone_config"] = [z if isinstance(z, dict) else z.model_dump() for z in updates["zone_config"]]
    if updates:
        service.table("cctv_cameras").update(updates).eq("id", camera_id).execute()

    result = service.table("cctv_cameras").select("*").eq("id", camera_id).execute()
    return _to_response(result.data[0])

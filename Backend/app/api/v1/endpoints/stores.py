"""Store search — customer Step 1 (search nearby stores)."""
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_current_customer
from app.core.security import AuthenticatedUser
from app.schemas.store import StoreSearchResult
from app.services import store_service

router = APIRouter(prefix="/stores", tags=["Stores"])


@router.get(
    "/search",
    response_model=list[StoreSearchResult],
    summary="Search nearby stores",
    description="Filter by name, store type, and optionally sort by distance when lat/lng are provided.",
)
def search_stores(
    q: str | None = Query(default=None, description="Search by store name"),
    store_type: str | None = Query(default=None, description="grocery | hypermarket | mini_mart"),
    lat: float | None = Query(default=None),
    lng: float | None = Query(default=None),
    max_distance_km: float | None = Query(default=None, gt=0),
    _user: AuthenticatedUser = Depends(get_current_customer),
) -> list[StoreSearchResult]:
    return store_service.search_stores(
        query=q, store_type=store_type, lat=lat, lng=lng, max_distance_km=max_distance_km
    )

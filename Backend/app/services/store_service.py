"""
Store search service.

Distance is computed in Python using the haversine formula rather than a
PostGIS/earthdistance query, so this works against a stock Supabase project
with no extra extensions enabled. This is fine at catalog sizes of a few
thousand stores; if store count grows large enough that "fetch all active
stores, then filter/sort in Python" becomes a bottleneck, replace the fetch
below with a Postgres RPC using the `earthdistance` extension and keep this
function's signature identical so callers don't need to change.
"""
import math

from app.db.supabase_client import get_service_client
from app.schemas.store import StoreSearchResult

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def search_stores(
    query: str | None = None,
    store_type: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    max_distance_km: float | None = None,
    limit: int = 50,
) -> list[StoreSearchResult]:
    service = get_service_client()
    q = service.table("stores").select("*").eq("is_active", True)

    if store_type:
        q = q.eq("store_type", store_type)
    if query:
        q = q.ilike("name", f"%{query}%")

    result = q.limit(limit).execute()
    rows = result.data or []

    results: list[StoreSearchResult] = []
    for row in rows:
        distance_km = None
        if lat is not None and lng is not None and row.get("latitude") is not None and row.get("longitude") is not None:
            distance_km = round(_haversine_km(lat, lng, row["latitude"], row["longitude"]), 2)
            if max_distance_km is not None and distance_km > max_distance_km:
                continue

        results.append(
            StoreSearchResult(
                id=row["id"],
                name=row["name"],
                store_type=row["store_type"],
                image_url=row.get("image_url"),
                address_line=row.get("address_line"),
                city=row.get("city"),
                rating=row.get("rating") or 0.0,
                opening_time=row.get("opening_time"),
                closing_time=row.get("closing_time"),
                distance_km=distance_km,
            )
        )

    if lat is not None and lng is not None:
        results.sort(key=lambda s: (s.distance_km is None, s.distance_km))

    return results

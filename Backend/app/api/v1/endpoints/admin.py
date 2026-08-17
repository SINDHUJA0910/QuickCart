"""Admin views — platform-wide, cross-retailer. See admin_deps.py for the
auth model and its explicitly-stated limitations."""
from fastapi import APIRouter, Depends

from app.api.v1.admin_deps import require_admin
from app.schemas.admin import AdminStoreSummary, PlatformStatsResponse, SystemHealthResponse
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=PlatformStatsResponse)
def platform_stats() -> PlatformStatsResponse:
    return admin_service.get_platform_stats()


@router.get("/stores", response_model=list[AdminStoreSummary])
def all_stores() -> list[AdminStoreSummary]:
    return admin_service.list_all_stores()


@router.get("/health", response_model=SystemHealthResponse)
def system_health() -> SystemHealthResponse:
    return admin_service.check_system_health()

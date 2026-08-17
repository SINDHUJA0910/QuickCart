"""Retailer dashboard — live stats, live sessions, recent transactions."""
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.dashboard import DashboardStatsResponse, LiveSessionResponse, RecentTransactionResponse
from app.services import dashboard_service

router = APIRouter(prefix="/retailer/stores/{store_id}/dashboard", tags=["Retailer — Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_stats(store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)) -> DashboardStatsResponse:
    return dashboard_service.get_dashboard_stats(store_id=store_id, retailer_id=user.id)


@router.get("/live-sessions", response_model=list[LiveSessionResponse])
def get_live_sessions(
    store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)
) -> list[LiveSessionResponse]:
    return dashboard_service.get_live_sessions(store_id=store_id, retailer_id=user.id)


@router.get("/transactions", response_model=list[RecentTransactionResponse])
def get_recent_transactions(
    store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)
) -> list[RecentTransactionResponse]:
    return dashboard_service.get_recent_transactions(store_id=store_id, retailer_id=user.id)

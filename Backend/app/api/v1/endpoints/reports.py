"""Retailer sales reports — CSV export, top products, peak shopping hours."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import io

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.dashboard import PeakHourStat, TopProductStat
from app.services import report_service

router = APIRouter(prefix="/retailer/stores/{store_id}/reports", tags=["Retailer — Reports"])


@router.get("/transactions.csv", summary="Download all successful transactions as CSV")
def download_transactions_csv(store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)):
    csv_text = report_service.export_transactions_csv(store_id=store_id, retailer_id=user.id)
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=quickcart_transactions_{store_id}.csv"},
    )


@router.get("/top-products", response_model=list[TopProductStat])
def top_products(store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)) -> list[TopProductStat]:
    return report_service.get_top_products(store_id=store_id, retailer_id=user.id)


@router.get("/peak-hours", response_model=list[PeakHourStat])
def peak_hours(store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)) -> list[PeakHourStat]:
    return report_service.get_peak_hours(store_id=store_id, retailer_id=user.id)

"""Retailer exit scan — spec Step 9 (retailer scans QR, closes the session)."""
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.checkout import ExitScanRequest, ExitScanResponse
from app.services import exit_service

router = APIRouter(prefix="/retailer/exit", tags=["Retailer — Exit Scan"])


@router.post(
    "/scan",
    response_model=ExitScanResponse,
    summary="Validate a customer's QR exit pass and close their session",
)
def scan_exit(
    payload: ExitScanRequest,
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> ExitScanResponse:
    return exit_service.scan_exit(qr_token=payload.qr_token, retailer_id=user.id)

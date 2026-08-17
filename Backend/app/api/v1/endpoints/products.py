"""Barcode lookup — customer Step 4 (scan product, show detail card before Add to Cart)."""
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_customer
from app.core.security import AuthenticatedUser
from app.schemas.product import ProductDetailResponse
from app.services import product_service

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


@router.get(
    "/barcode/{barcode}",
    response_model=ProductDetailResponse,
    summary="Look up a product by barcode within a store",
)
def get_product_by_barcode(
    store_id: str,
    barcode: str,
    _user: AuthenticatedUser = Depends(get_current_customer),
) -> ProductDetailResponse:
    return product_service.get_product_by_barcode(store_id=store_id, barcode=barcode)

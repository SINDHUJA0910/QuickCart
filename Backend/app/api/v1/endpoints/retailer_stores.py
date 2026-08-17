"""Retailer store management (create/list/update the retailer's own stores)."""
from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.store import RetailerStoreResponse, StoreCreateRequest, StoreUpdateRequest
from app.services import retailer_store_service

router = APIRouter(prefix="/retailer/stores", tags=["Retailer — Stores"])


@router.post("", response_model=RetailerStoreResponse, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: StoreCreateRequest, user: AuthenticatedUser = Depends(get_current_retailer)
) -> RetailerStoreResponse:
    return retailer_store_service.create_store(retailer_id=user.id, payload=payload)


@router.get("", response_model=list[RetailerStoreResponse])
def list_my_stores(user: AuthenticatedUser = Depends(get_current_retailer)) -> list[RetailerStoreResponse]:
    return retailer_store_service.list_my_stores(retailer_id=user.id)


@router.patch("/{store_id}", response_model=RetailerStoreResponse)
def update_store(
    store_id: str, payload: StoreUpdateRequest, user: AuthenticatedUser = Depends(get_current_retailer)
) -> RetailerStoreResponse:
    return retailer_store_service.update_store(store_id=store_id, retailer_id=user.id, payload=payload)

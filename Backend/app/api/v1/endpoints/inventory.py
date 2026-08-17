"""Retailer inventory management — products and categories."""
from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.inventory import (
    CategoryCreateRequest,
    CategoryResponse,
    ProductCreateRequest,
    ProductUpdateRequest,
    RetailerProductResponse,
)
from app.services import inventory_service

router = APIRouter(prefix="/retailer/stores/{store_id}", tags=["Retailer — Inventory"])


@router.post("/products", response_model=RetailerProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    store_id: str, payload: ProductCreateRequest, user: AuthenticatedUser = Depends(get_current_retailer)
) -> RetailerProductResponse:
    return inventory_service.create_product(store_id=store_id, retailer_id=user.id, payload=payload)


@router.get("/products", response_model=list[RetailerProductResponse])
def list_products(
    store_id: str,
    low_stock_only: bool = Query(default=False),
    include_inactive: bool = Query(default=False, description="Include soft-deleted products"),
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> list[RetailerProductResponse]:
    return inventory_service.list_products(
        store_id=store_id, retailer_id=user.id, low_stock_only=low_stock_only, include_inactive=include_inactive
    )


@router.patch("/products/{product_id}", response_model=RetailerProductResponse)
def update_product(
    store_id: str,
    product_id: str,
    payload: ProductUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> RetailerProductResponse:
    return inventory_service.update_product(
        store_id=store_id, product_id=product_id, retailer_id=user.id, payload=payload
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    store_id: str, product_id: str, user: AuthenticatedUser = Depends(get_current_retailer)
) -> None:
    inventory_service.delete_product(store_id=store_id, product_id=product_id, retailer_id=user.id)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    store_id: str, payload: CategoryCreateRequest, user: AuthenticatedUser = Depends(get_current_retailer)
) -> CategoryResponse:
    return inventory_service.create_category(store_id=store_id, retailer_id=user.id, payload=payload)


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)
) -> list[CategoryResponse]:
    return inventory_service.list_categories(store_id=store_id, retailer_id=user.id)

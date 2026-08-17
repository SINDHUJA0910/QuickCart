"""Retailer CCTV camera management."""
from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.camera import CameraCreateRequest, CameraResponse, CameraUpdateRequest
from app.services import camera_service

router = APIRouter(prefix="/retailer/stores/{store_id}/cameras", tags=["Retailer — CCTV Cameras"])


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    store_id: str, payload: CameraCreateRequest, user: AuthenticatedUser = Depends(get_current_retailer)
) -> CameraResponse:
    return camera_service.create_camera(store_id=store_id, retailer_id=user.id, payload=payload)


@router.get("", response_model=list[CameraResponse])
def list_cameras(store_id: str, user: AuthenticatedUser = Depends(get_current_retailer)) -> list[CameraResponse]:
    return camera_service.list_cameras(store_id=store_id, retailer_id=user.id)


@router.patch("/{camera_id}", response_model=CameraResponse)
def update_camera(
    store_id: str,
    camera_id: str,
    payload: CameraUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> CameraResponse:
    return camera_service.update_camera(store_id=store_id, camera_id=camera_id, retailer_id=user.id, payload=payload)

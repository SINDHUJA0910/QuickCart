"""Virtual cart — customer Steps 4-5 (Add to Cart, view/edit cart)."""
from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_customer
from app.core.security import AuthenticatedUser
from app.schemas.cart import CartItemAddRequest, CartItemUpdateRequest, CartSummaryResponse
from app.services import cart_service

router = APIRouter(prefix="/sessions/{session_id}/cart", tags=["Cart"])


@router.get(
    "",
    response_model=CartSummaryResponse,
    summary="Get the current cart for a session",
)
def get_cart(session_id: str, user: AuthenticatedUser = Depends(get_current_customer)) -> CartSummaryResponse:
    return cart_service.get_cart_summary(session_id=session_id, customer_id=user.id)


@router.post(
    "/items",
    response_model=CartSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a scanned product to the cart",
)
def add_item(
    session_id: str,
    payload: CartItemAddRequest,
    user: AuthenticatedUser = Depends(get_current_customer),
) -> CartSummaryResponse:
    return cart_service.add_item(
        session_id=session_id, customer_id=user.id, product_id=payload.product_id, quantity=payload.quantity
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartSummaryResponse,
    summary="Update a cart item's quantity",
)
def update_item(
    session_id: str,
    item_id: str,
    payload: CartItemUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_customer),
) -> CartSummaryResponse:
    return cart_service.update_item_quantity(
        session_id=session_id, customer_id=user.id, item_id=item_id, new_quantity=payload.quantity
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartSummaryResponse,
    summary="Remove an item from the cart",
)
def remove_item(
    session_id: str,
    item_id: str,
    user: AuthenticatedUser = Depends(get_current_customer),
) -> CartSummaryResponse:
    return cart_service.remove_item(session_id=session_id, customer_id=user.id, item_id=item_id)

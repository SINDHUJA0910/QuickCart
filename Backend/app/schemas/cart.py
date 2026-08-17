"""Schemas for the virtual cart."""
from pydantic import BaseModel, Field


class CartItemAddRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, gt=0, le=99)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(gt=0, le=99)


class CartItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_image_url: str | None
    quantity: int
    unit_price_paise: int
    line_total_paise: int


class CartSummaryResponse(BaseModel):
    session_id: str
    items: list[CartItemResponse]
    item_count: int
    subtotal_paise: int    # sum of MRP * qty, before discount
    discount_paise: int    # total savings from per-product discounts
    gst_paise: int
    total_paise: int       # subtotal - discount + gst

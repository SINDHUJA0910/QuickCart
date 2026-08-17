"""Schemas for product lookup (the barcode-scan product detail card)."""
from datetime import date

from pydantic import BaseModel


class ProductDetailResponse(BaseModel):
    id: str
    barcode: str
    name: str
    brand: str | None
    image_url: str | None
    description: str | None
    mrp_paise: int
    discount_percent: float
    price_paise: int
    gst_percent: float
    weight_value: float | None
    weight_unit: str | None
    manufacture_date: date | None
    expiry_date: date | None
    in_stock: bool
    stock_quantity: int

"""Schemas for retailer inventory management (products + categories)."""
from datetime import date

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None


class ProductCreateRequest(BaseModel):
    barcode: str | None = Field(default=None, description="Leave blank to auto-generate a valid EAN-13 code")
    category_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = None
    description: str | None = None
    image_url: str | None = None
    mrp_paise: int = Field(gt=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    gst_percent: float = Field(default=0, ge=0, le=100)
    weight_value: float | None = None
    weight_unit: str | None = None
    manufacture_date: date | None = None
    expiry_date: date | None = None
    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    supplier_name: str | None = None
    supplier_contact: str | None = None
    shelf_location: str | None = None


class ProductUpdateRequest(BaseModel):
    category_id: str | None = None
    name: str | None = None
    brand: str | None = None
    description: str | None = None
    image_url: str | None = None
    mrp_paise: int | None = Field(default=None, gt=0)
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    gst_percent: float | None = Field(default=None, ge=0, le=100)
    weight_value: float | None = None
    weight_unit: str | None = None
    manufacture_date: date | None = None
    expiry_date: date | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    supplier_name: str | None = None
    supplier_contact: str | None = None
    shelf_location: str | None = None
    is_active: bool | None = None


class RetailerProductResponse(BaseModel):
    id: str
    barcode: str
    name: str
    brand: str | None
    category_id: str | None
    image_url: str | None
    mrp_paise: int
    discount_percent: float
    price_paise: int
    gst_percent: float
    stock_quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    supplier_name: str | None
    expiry_date: date | None
    is_active: bool

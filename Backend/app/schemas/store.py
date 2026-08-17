"""Schemas for store search and retailer store management."""
from pydantic import BaseModel, Field


class StoreSearchResult(BaseModel):
    id: str
    name: str
    store_type: str
    image_url: str | None
    address_line: str | None
    city: str | None
    rating: float
    opening_time: str | None
    closing_time: str | None
    distance_km: float | None  # null when no lat/lng provided in the search request


class StoreCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    store_type: str = Field(description="grocery | hypermarket | mini_mart")
    image_url: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_time: str | None = None
    closing_time: str | None = None


class StoreUpdateRequest(BaseModel):
    name: str | None = None
    image_url: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_time: str | None = None
    closing_time: str | None = None
    is_active: bool | None = None


class RetailerStoreResponse(BaseModel):
    id: str
    name: str
    store_type: str
    is_active: bool
    address_line: str | None
    city: str | None
    rating: float

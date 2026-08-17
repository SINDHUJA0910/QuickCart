"""Schemas for CCTV camera management and shelf zone configuration."""
from pydantic import BaseModel, Field


class ZoneConfig(BaseModel):
    zone_id: str
    x1: int
    y1: int
    x2: int
    y2: int
    shelf_location: str | None = None


class CameraCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    stream_url: str
    zone_config: list[ZoneConfig] = Field(default_factory=list)


class CameraUpdateRequest(BaseModel):
    label: str | None = None
    stream_url: str | None = None
    zone_config: list[ZoneConfig] | None = None
    status: str | None = None


class CameraResponse(BaseModel):
    id: str
    label: str
    status: str
    stream_url: str
    zone_config: list[ZoneConfig]

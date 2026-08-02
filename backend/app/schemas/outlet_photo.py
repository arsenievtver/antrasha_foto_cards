from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OutletPhotoStatusOut(BaseModel):
    moysklad_configured: bool
    fashn_configured: bool
    ready: bool


class OutletPhotoLookupIn(BaseModel):
    barcode: str = Field(..., min_length=1, max_length=64)


class OutletPhotoLookupOut(BaseModel):
    product_id: str
    name: str
    article: str | None = None
    code: str | None = None
    barcode: str
    entity_type: str
    variant_id: str | None = None
    path_name: str | None = None
    gender: str | None = None


class OutletPhotoGenerateOut(BaseModel):
    image_base64: str
    mime: str = "image/png"
    filename: str


class OutletPhotoUploadIn(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    filename: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class OutletPhotoUploadOut(BaseModel):
    product_id: str
    images_count: int
    images: list[dict[str, Any]] = Field(default_factory=list)

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CollectionPhotoStatusOut(BaseModel):
    moysklad_configured: bool
    ready: bool


class CollectionPhotoLookupIn(BaseModel):
    barcode: str = Field(min_length=1, max_length=64)


class CollectionPhotoLookupOut(BaseModel):
    product_id: str
    name: str
    article: str | None = None
    code: str | None = None
    barcode: str
    path_name: str | None = None
    gender: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    brand_id: uuid.UUID | None = None
    brand_name: str | None = None
    brand_match: str
    brand_warning: str | None = None
    existing_images_count: int = 0
    existing_image_preview: str | None = None

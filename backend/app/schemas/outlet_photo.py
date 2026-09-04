from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

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
    existing_images_count: int = 0
    existing_image_preview: str | None = None


class OutletPhotoGenerateOut(BaseModel):
    image_base64: str
    mime: str = "image/png"
    filename: str


class OutletPhotoUploadIn(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    filename: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    # Снимок карточки на момент загрузки (из lookup) — для журнала переноса.
    name: str | None = Field(default=None, max_length=500)
    article: str | None = Field(default=None, max_length=120)
    code: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=64)
    path_name: str | None = None
    gender: str | None = Field(default=None, max_length=10)


class OutletPhotoUploadOut(BaseModel):
    product_id: str
    images_count: int
    images: list[dict[str, Any]] = Field(default_factory=list)
    upload_id: uuid.UUID | None = None


class OutletPhotoUploadItemOut(BaseModel):
    id: uuid.UUID
    product_id: str
    product_name: str
    article: str | None = None
    code: str | None = None
    barcode: str | None = None
    path_name: str | None = None
    gender: str | None = None
    uploaded_by_user_id: uuid.UUID | None = None
    uploaded_by_label: str
    transferred: bool
    transferred_at: datetime | None = None
    created_at: datetime


class OutletPhotoUploadListOut(BaseModel):
    items: list[OutletPhotoUploadItemOut]
    total: int
    skip: int
    limit: int
    filter: Literal["pending", "transferred", "all"] = "pending"


class OutletPhotoUploadTransferredIn(BaseModel):
    transferred: bool

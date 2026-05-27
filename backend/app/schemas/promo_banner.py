import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.promo_banner import PromoBannerDisplayMode


class PromoBannerPublicOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    image_url: str | None
    link_url: str | None
    link_label: str | None

    model_config = {"from_attributes": True}


class PromoBannerActiveResponse(BaseModel):
    banner: PromoBannerPublicOut | None


class AdminPromoBannerOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    image_url: str | None
    link_url: str | None
    link_label: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    display_mode: PromoBannerDisplayMode
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminPromoBannerListResponse(BaseModel):
    items: list[AdminPromoBannerOut]


class AdminPromoBannerCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    display_mode: PromoBannerDisplayMode = PromoBannerDisplayMode.once
    is_active: bool = True
    priority: int = 0


class AdminPromoBannerUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    display_mode: PromoBannerDisplayMode | None = None
    is_active: bool | None = None
    priority: int | None = None
    clear_image: bool = False


class AdminPromoBannerImageUploadResponse(BaseModel):
    image_url: str

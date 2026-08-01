import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class HeroBannerPublicOut(BaseModel):
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    body: str | None = None
    image_url: str | None = None
    image_url_desktop: str | None = None
    link_url: str | None = None
    link_label: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class HeroBannerActiveResponse(BaseModel):
    items: list[HeroBannerPublicOut]


class AdminHeroBannerOut(BaseModel):
    id: uuid.UUID
    title: str
    subtitle: str | None
    body: str | None
    image_url: str | None
    image_url_desktop: str | None
    link_url: str | None
    link_label: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminHeroBannerListResponse(BaseModel):
    items: list[AdminHeroBannerOut]


class AdminHeroBannerCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=120)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    image_url_desktop: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    priority: int = 0


class AdminHeroBannerUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=120)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    image_url_desktop: str | None = Field(default=None, max_length=500)
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    priority: int | None = None
    clear_image: bool = False
    clear_image_desktop: bool = False


class AdminHeroBannerImageUploadResponse(BaseModel):
    image_url: str | None = None
    image_url_desktop: str | None = None

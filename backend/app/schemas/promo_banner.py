import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.promo_banner import PromoBannerDisplayMode

ImageFit = Literal["fit", "cover"]


class PromoBannerPublicOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    image_url: str | None
    image_fit: ImageFit = "fit"
    link_url: str | None
    link_label: str | None
    show_gender_ctas: bool = False
    cta_male_label: str | None = None
    cta_female_label: str | None = None

    model_config = {"from_attributes": True}


class PromoBannerActiveResponse(BaseModel):
    banner: PromoBannerPublicOut | None


class AdminPromoBannerOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    image_url: str | None
    image_fit: ImageFit = "fit"
    link_url: str | None
    link_label: str | None
    show_gender_ctas: bool = False
    cta_male_label: str | None = None
    cta_female_label: str | None = None
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


def _norm_image_fit(v: str | None) -> str:
    if not v:
        return "fit"
    s = str(v).strip().lower()
    return s if s in ("fit", "cover") else "fit"


class AdminPromoBannerCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    image_fit: ImageFit = "fit"
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    show_gender_ctas: bool = False
    cta_male_label: str | None = Field(default=None, max_length=80)
    cta_female_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    display_mode: PromoBannerDisplayMode = PromoBannerDisplayMode.once
    is_active: bool = True
    priority: int = 0

    @field_validator("image_fit", mode="before")
    @classmethod
    def validate_image_fit(cls, v: object) -> str:
        return _norm_image_fit(v if isinstance(v, str) or v is None else str(v))


class AdminPromoBannerUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    image_fit: ImageFit | None = None
    link_url: str | None = Field(default=None, max_length=500)
    link_label: str | None = Field(default=None, max_length=80)
    show_gender_ctas: bool | None = None
    cta_male_label: str | None = Field(default=None, max_length=80)
    cta_female_label: str | None = Field(default=None, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    display_mode: PromoBannerDisplayMode | None = None
    is_active: bool | None = None
    priority: int | None = None
    clear_image: bool = False

    @field_validator("image_fit", mode="before")
    @classmethod
    def validate_image_fit(cls, v: object) -> str | None:
        if v is None:
            return None
        return _norm_image_fit(v if isinstance(v, str) else str(v))


class AdminPromoBannerImageUploadResponse(BaseModel):
    image_url: str

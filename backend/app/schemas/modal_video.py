import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CtaMode = Literal["close", "lead"]


class ModalVideoPublicOut(BaseModel):
    slug: str
    title: str
    body: str | None = None
    video_url: str | None = None
    poster_url: str | None = None
    cta_mode: CtaMode
    cta_label: str | None = None
    lead_note: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminModalVideoOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    body: str | None
    video_url: str | None
    poster_url: str | None
    cta_mode: CtaMode
    cta_label: str | None
    lead_note: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminModalVideoListResponse(BaseModel):
    items: list[AdminModalVideoOut]


class AdminModalVideoCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None
    cta_mode: CtaMode = "close"
    cta_label: str | None = Field(default=None, max_length=80)
    lead_note: str | None = Field(default=None, max_length=200)
    is_active: bool = True


class AdminModalVideoUpdateRequest(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    cta_mode: CtaMode | None = None
    cta_label: str | None = Field(default=None, max_length=80)
    lead_note: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    clear_video: bool = False
    clear_poster: bool = False


class AdminModalVideoUploadResponse(BaseModel):
    video_url: str | None = None
    poster_url: str | None = None

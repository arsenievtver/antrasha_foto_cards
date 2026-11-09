from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CaretakerOut(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_label: str
    source: str
    active: bool
    created_at: datetime | None = None


class CaretakerIn(BaseModel):
    author_user_id: uuid.UUID | None = None
    author_label: str = Field(..., max_length=160)

    @field_validator("author_label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Нужно имя сотрудника")
        return value


class AClientListItem(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    status: str | None
    active: bool
    last_visit: str | None
    days_since: int | None
    median_gap: float | None = None
    visits: int | None = None
    rev_prev12: float | None
    rev_cur12: float | None
    brands: list[str] = []
    categories: list[str] = []
    sizes: str | None = None
    avg_discount_pct: float | None = None
    markdown_share_pct: float | None = None
    picks: list[PickOut] = []
    first_week: str | None
    last_week: str | None
    weeks_on_list: int
    caretakers: list[CaretakerOut]
    comment_count: int
    last_comment_at: datetime | None = None
    last_comment_text: str | None
    last_comment_author: str | None


class AClientListOut(BaseModel):
    items: list[AClientListItem]
    total: int


class AClientWeekOut(BaseModel):
    week_start: str
    status: str | None
    last_visit: str | None
    days_since: int | None
    visits: int | None
    rev_prev12: float | None
    rev_cur12: float | None


class AClientProgressOut(BaseModel):
    weeks_on_list: int
    on_list_now: bool
    first_week: str | None
    last_week: str | None
    rev_cur12_first: float | None
    rev_cur12_last: float | None
    days_since_first: int | None
    days_since_last: int | None
    status_first: str | None
    status_last: str | None


class CommentPartOut(BaseModel):
    id: uuid.UUID
    text: str
    created_at: datetime | None = None


class CommentGroupOut(BaseModel):
    thread_id: uuid.UUID | None
    author_label: str
    author_user_id: uuid.UUID | None
    created_at: datetime | None = None
    binding: str | None
    parts: list[CommentPartOut]


class PickOut(BaseModel):
    name: str | None = None
    price: float | None = None
    old: bool | None = None
    age_m: float | None = None
    brand_match: bool | None = None


class AClientDetailOut(BaseModel):
    id: uuid.UUID
    counterparty_id: str
    name: str
    phone: str | None
    status: str | None
    active: bool
    last_visit: str | None
    days_since: int | None
    median_gap: float | None
    visits: int | None
    rev_prev12: float | None
    rev_cur12: float | None
    brands: list[str]
    categories: list[str]
    sizes: str | None
    avg_discount_pct: float | None
    markdown_share_pct: float | None
    picks: list[PickOut]
    first_week: str | None
    last_week: str | None
    caretakers: list[CaretakerOut]
    weeks: list[AClientWeekOut]
    progress: AClientProgressOut
    comments: list[CommentGroupOut]


class AClientSyncOut(BaseModel):
    reports: int
    clients: int
    active: int
    merged_messages: int = 0
    linked_messages: int = 0
    caretakers: int = 0


class ActiveBoardOut(BaseModel):
    ready: bool
    week_start: str | None = None
    prev_week_start: str | None = None
    summary: dict | None = None
    items: list[dict]
    left: list[dict]

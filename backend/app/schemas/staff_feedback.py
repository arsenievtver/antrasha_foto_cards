from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_TEXT = 4000


class StaffFeedbackTextIn(BaseModel):
    text: str = Field(..., max_length=MAX_TEXT)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Пустое сообщение")
        return value


class StaffFeedbackOut(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_label: str
    text: str
    created_at: datetime
    updated_at: datetime | None


class StaffFeedbackListOut(BaseModel):
    items: list[StaffFeedbackOut]
    total: int
    skip: int
    limit: int


class StaffFeedbackStatOut(BaseModel):
    author_user_id: uuid.UUID | None
    author_label: str
    messages: int
    active_days: int
    total_chars: int
    first_at: datetime | None
    last_at: datetime | None


class StaffFeedbackStatsOut(BaseModel):
    items: list[StaffFeedbackStatOut]

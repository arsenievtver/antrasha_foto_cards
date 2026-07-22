import uuid
from typing import Any

from pydantic import BaseModel, Field


class TagOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    weight: float = Field(description="How strongly this tag applies to the photo")


class FeedPhoto(BaseModel):
    id: uuid.UUID
    url: str
    gender: str
    source_type: str
    # Денормализация из brands.name; не путать с тегами каталога (photo_tags).
    brand: str | None = None
    # Свободный бейдж на карточке (Sale, −30%…); только отображение.
    # Резолвится на бэке: show_badge + feed_settings.card_badge_label.
    badge_label: str | None = None
    tags: list[TagOut]


class FeedResponse(BaseModel):
    photos: list[FeedPhoto]
    meta: dict[str, Any] = Field(default_factory=dict)

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.modal_video import ModalVideo

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str) -> str:
    return (value or "").strip().lower()


def validate_slug(value: str) -> str:
    slug = normalize_slug(value)
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(
            "Slug: латиница, цифры и дефис (например about или lookbook-ss26)",
        )
    return slug


def get_active_by_slug(db: Session, slug: str) -> ModalVideo | None:
    normalized = normalize_slug(slug)
    if not normalized:
        return None
    row = db.scalar(select(ModalVideo).where(ModalVideo.slug == normalized))
    if not row or not row.is_active or not row.video_url:
        return None
    return row

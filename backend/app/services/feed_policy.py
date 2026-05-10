"""Политика выдачи ленты: фильтр по tagging_review_done."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.feed_settings import FeedSettings


def feed_require_tagging_review_for_feed(db: Session) -> bool:
    """True — в ленту только фото с tagging_review_done; False — без этого ограничения."""
    row = db.get(FeedSettings, 1)
    if row is None:
        return False
    return bool(row.require_tagging_review_for_feed)

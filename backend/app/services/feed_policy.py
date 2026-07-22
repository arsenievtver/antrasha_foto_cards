"""Политика выдачи ленты: фильтр по tagging_review_done и текст бейджа."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.feed_settings import FeedSettings


def feed_require_tagging_review_for_feed(db: Session) -> bool:
    """True — в ленту только фото с tagging_review_done; False — без этого ограничения."""
    row = db.get(FeedSettings, 1)
    if row is None:
        return False
    return bool(row.require_tagging_review_for_feed)


def feed_card_badge_label(db: Session) -> str | None:
    """Единый текст бейджа для карточек с show_badge; None если не задан."""
    row = db.get(FeedSettings, 1)
    if row is None or not row.card_badge_label:
        return None
    text = row.card_badge_label.strip()
    return text or None

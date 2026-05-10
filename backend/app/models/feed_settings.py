"""Singleton-настройки выдачи ленты (одна строка id=1)."""

from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedSettings(Base):
    __tablename__ = "feed_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # True → в /feed только фото с tagging_review_done; False → достаточно is_active + синка из бакета.
    require_tagging_review_for_feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

"""Singleton-настройки выдачи ленты (одна строка id=1)."""

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedSettings(Base):
    __tablename__ = "feed_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # True → в /feed только фото с tagging_review_done; False → достаточно is_active + синка из бакета.
    require_tagging_review_for_feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Единый текст бейджа на карточках (Sale, −50%…); показ — photos.show_badge.
    card_badge_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # tags | vectors | hybrid — как смешивать score в /feed (по умолчанию tags до backfill эмбеддингов).
    feed_ranking_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="tags")
    # Доля векторного score в hybrid (0..1); tag_score берёт остаток.
    feed_vector_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.65)
    swipe_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # True — male/female taste vectors; False — один общий профиль на обе коллекции.
    taste_vectors_separate_by_gender: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

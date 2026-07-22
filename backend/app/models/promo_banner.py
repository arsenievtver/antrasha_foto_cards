import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PromoBannerDisplayMode(str, enum.Enum):
    once = "once"
    twice = "twice"
    every_visit = "every_visit"


class PromoBanner(Base):
    __tablename__ = "promo_banners"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # fit | cover — как показывать картинку в модалке
    image_fit: Mapped[str] = mapped_column(String(16), nullable=False, default="fit")
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Кнопки перехода в мужскую / женскую коллекцию (поверх «Закрыть»).
    show_gender_ctas: Mapped[bool] = mapped_column(nullable=False, default=False)
    cta_male_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cta_female_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    display_mode: Mapped[PromoBannerDisplayMode] = mapped_column(
        Enum(
            PromoBannerDisplayMode,
            name="promo_banner_display_mode",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PromoBannerDisplayMode.once,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    impressions = relationship("PromoBannerImpression", back_populates="banner", cascade="all, delete-orphan")


class PromoBannerImpression(Base):
    __tablename__ = "promo_banner_impressions"
    __table_args__ = (
        UniqueConstraint("banner_id", "session_id", name="uq_promo_banner_impression_banner_session"),
        UniqueConstraint("banner_id", "user_id", name="uq_promo_banner_impression_banner_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    banner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("promo_banners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    banner = relationship("PromoBanner", back_populates="impressions")

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Единственный поддерживаемый источник файлов — Yandex Object Storage (синхронизация бакетов).
PHOTO_SOURCE_YC_OBJECT_STORAGE = "yc_object_storage"


class TagGroup(Base):
    """Группа тегов: ограничения min/max на одно фото, секция для UI."""

    __tablename__ = "tag_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    section: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    section_sort: Mapped[int] = mapped_column(default=0, nullable=False)
    group_sort: Mapped[int] = mapped_column(default=0, nullable=False)
    min_tags: Mapped[int] = mapped_column(default=0, nullable=False)
    max_tags: Mapped[int] = mapped_column(default=99, nullable=False)
    # base | strong | weak — влияние на обновление весов при свайпе (см. app.recommendation_model)
    swipe_tier: Mapped[str] = mapped_column(String(16), default="strong", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tags = relationship("Tag", back_populates="group")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PHOTO_SOURCE_YC_OBJECT_STORAGE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tagging_claimed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tagging_claimed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    tagging_review_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tagging_uncertain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worker_signal_love: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    worker_signal_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    worker_signal_hard: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Текст — денормализация имени бренда для API/списков; источник истины — brand_id.
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    price_segment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Внешний идентификатор для связи с «МойСклад» / товарным учётом (товар, модификация и т.д.).
    moy_sklad_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Инкремент при каждом сохранении тегов — optimistic locking в админке.
    tags_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Денормализация: уникальные «идентичности» (user_id или session_id),
    # которые последним действием поставили лайк/дизлайк. Источник истины — interactions:
    # повторные свайпы одной идентичности не считаются, «переключение» меняет сторону.
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislikes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    brand_row = relationship("Brand", back_populates="photos")
    photo_tags = relationship("PhotoTag", back_populates="photo", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="photo")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tag_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subgroup_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    recommendation_weight: Mapped[int] = mapped_column(default=50, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    group = relationship("TagGroup", back_populates="tags")
    photo_tags = relationship("PhotoTag", back_populates="tag")
    user_weights = relationship("UserTagWeight", back_populates="tag")


class PhotoTag(Base):
    __tablename__ = "photo_tags"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)

    photo = relationship("Photo", back_populates="photo_tags")
    tag = relationship("Tag", back_populates="photo_tags")

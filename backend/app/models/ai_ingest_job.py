import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AiIngestJob(Base):
    """Очередь: сырьё с телефона → Fashn → Object Storage."""

    __tablename__ = "ai_ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    gender: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # single (одна вещь-герой) | look (готовый образ) — правило для промпта Fashn.
    source_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="single",
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Переносится на Photo.show_badge после успешной загрузки в каталог.
    show_badge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    temp_path: Mapped[str] = mapped_column(Text, nullable=False)
    # inbox — кадр с телефона ждёт в админке. pending | processing | completed | failed — очередь Fashn.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Оплаченный заказ Fashn. Пока он есть, повтор только ждёт и скачивает результат.
    fashn_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # upload | submit | generating | download | save | embed — для админки и поиска зависших.
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feed_release_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Снимок товара с ценника. Пусто у загрузки с компьютера — в МойСклад она не ходит.
    moysklad_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    moysklad_supplier_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    article: Mapped[str | None] = mapped_column(String(120), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    path_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # uploaded | failed. Пусто — в МойСклад ещё не отправляли или это не съёмка коллекции.
    moysklad_upload_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    moysklad_upload_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    brand = relationship("Brand", lazy="joined", back_populates="ingest_jobs")
    release_batch = relationship("FeedReleaseBatch", back_populates="ingest_jobs")

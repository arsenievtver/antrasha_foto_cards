import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeedReleaseBatch(Base):
    """Пакет фото из AI ingest: draft до «Записать вектора и выпустить», затем published."""

    __tablename__ = "feed_release_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gender: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # draft — ждёт embed+publish; published — в ленте.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_embed_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    photos = relationship("Photo", back_populates="release_batch")
    ingest_jobs = relationship("AiIngestJob", back_populates="release_batch")

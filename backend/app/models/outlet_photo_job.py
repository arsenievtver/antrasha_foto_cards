"""Очередь аутлета: телефон отдал кадр, сервер сам ходит в Fashn."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# pending → running → ready | failed. Дальше uploaded или cancelled.
OPEN_JOB_STATUSES = ("pending", "running", "ready", "failed")


class OutletPhotoJob(Base):
    __tablename__ = "outlet_photo_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    article: Mapped[str | None] = mapped_column(String(120), nullable=True)
    code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    path_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)

    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    result_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

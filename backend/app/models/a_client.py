"""Клиенты категории А на контроле и кто из сотрудников их ведёт."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AClient(Base):
    __tablename__ = "a_clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # id контрагента в МойСклад — тот же, что в списке недели.
    counterparty_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_visit: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_since: Mapped[int | None] = mapped_column(Integer, nullable=True)
    median_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    visits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rev_prev12: Mapped[float | None] = mapped_column(Float, nullable=True)
    rev_cur12: Mapped[float | None] = mapped_column(Float, nullable=True)
    brands: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sizes: Mapped[str | None] = mapped_column(Text, nullable=True)
    avg_discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    markdown_share_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    picks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # False — в последней готовой неделе клиента уже нет в списке.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_week: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_week: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AClientWeek(Base):
    """Срез клиента на неделю отчёта: по нему видно, меняется ли статус и выручка."""

    __tablename__ = "a_client_weeks"
    __table_args__ = (UniqueConstraint("client_id", "week_start", name="uq_a_client_weeks_client_week"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("a_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_insight_reports.id", ondelete="SET NULL"), nullable=True
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_visit: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_since: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rev_prev12: Mapped[float | None] = mapped_column(Float, nullable=True)
    rev_cur12: Mapped[float | None] = mapped_column(Float, nullable=True)


class AClientCaretaker(Base):
    """Сотрудник, который ведёт клиента. Несколько строк на одного клиента — норма."""

    __tablename__ = "a_client_caretakers"
    __table_args__ = (UniqueConstraint("client_id", "author_key", name="uq_a_client_caretakers_author"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("a_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    author_label: Mapped[str] = mapped_column(String(160), nullable=False)
    # uuid сотрудника или «label:…», если учётки уже нет.
    author_key: Mapped[str] = mapped_column(String(180), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="comment")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Сняли вручную — повторный разбор комментариев не вернёт.
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

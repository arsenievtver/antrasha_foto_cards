"""Недельный отчёт по МойСклад: метрики, список клиентов на контроле и текст сводки."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

WEEKLY_INSIGHT_STATUSES = ("running", "done", "error")


class WeeklyInsightReport(Base):
    __tablename__ = "weekly_insight_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Понедельник отчётной недели (пн–вс перед запуском).
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    started_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # ФИО и телефоны — отдельно от метрик, чтобы MCP отдавал их только по запросу.
    watchlist: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ms_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

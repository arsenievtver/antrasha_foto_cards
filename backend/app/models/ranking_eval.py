import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RankingEvalBenchmark(Base):
    __tablename__ = "ranking_eval_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items = relationship(
        "RankingEvalBenchmarkItem",
        back_populates="benchmark",
        cascade="all, delete-orphan",
        order_by="RankingEvalBenchmarkItem.sort_order",
    )
    submissions = relationship(
        "RankingEvalSubmission",
        back_populates="benchmark",
        cascade="all, delete-orphan",
    )


class RankingEvalBenchmarkItem(Base):
    __tablename__ = "ranking_eval_benchmark_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ranking_eval_benchmarks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    benchmark = relationship("RankingEvalBenchmark", back_populates="items")
    photo = relationship("Photo")


class RankingEvalSubmission(Base):
    __tablename__ = "ranking_eval_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ranking_eval_benchmarks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    human_order: Mapped[list] = mapped_column(JSONB, nullable=False)
    model_order: Mapped[list] = mapped_column(JSONB, nullable=False)
    settings_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    kendall_tau: Mapped[float | None] = mapped_column(nullable=True)
    spearman_rho: Mapped[float | None] = mapped_column(nullable=True)
    top3_overlap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    benchmark = relationship("RankingEvalBenchmark", back_populates="submissions")
    user = relationship("User")

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Shipment(Base):
    """Поставка от бренда: сумма в евро, вес в кг и курс на дату поставки."""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipped_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    eur_rub_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    amount_rub: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    logistics_amount_rub: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 2), nullable=True
    )
    logistics_paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order = relationship("BrandOrder", back_populates="shipments")
    season = relationship("Season", back_populates="shipments")
    brand = relationship("Brand", back_populates="shipments")

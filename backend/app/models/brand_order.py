import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ORDER_GENDER_MEN = "men"
ORDER_GENDER_WOMEN = "women"
ORDER_GENDER_MIXED = "mixed"
ORDER_GENDERS = (ORDER_GENDER_MEN, ORDER_GENDER_WOMEN, ORDER_GENDER_MIXED)


class BrandOrder(Base):
    """Заказ у иностранного бренда на сезон.

    `amount_eur` — сумма заказа; при переданных строках пересчитывается как сумма
    строк по категориям. Предоплата здесь — план (сумма и срок), факт оплаты
    живёт в `payments` с kind=prepayment.
    """

    __tablename__ = "brand_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ordered_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    eur_rub_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    has_prepayment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prepayment_amount_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    prepayment_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    season = relationship("Season", back_populates="orders")
    brand = relationship("Brand", back_populates="orders")
    lines = relationship(
        "BrandOrderCategoryLine",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payments = relationship("Payment", back_populates="order")
    shipments = relationship("Shipment", back_populates="order")


class BrandOrderCategoryLine(Base):
    """Разбивка заказа по закупочным категориям."""

    __tablename__ = "brand_order_category_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order = relationship("BrandOrder", back_populates="lines")
    category = relationship("Category", back_populates="order_lines")

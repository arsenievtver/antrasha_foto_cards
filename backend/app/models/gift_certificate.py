import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Identity, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GiftCertificateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class GiftTransactionStatus(str, enum.Enum):
    OPENED = "OPENED"
    CANCELLED = "CANCELLED"
    DONE = "DONE"


class GiftCertificate(Base):
    __tablename__ = "gift_certificates"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nominal: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    check_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GiftCertificateStatus.ACTIVE.value
    )
    created_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    used_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    indefinite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str] = mapped_column(String(256), nullable=False)
    actual_tran_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    transactions: Mapped[list["GiftCertificateTransaction"]] = relationship(
        back_populates="certificate",
        cascade="all, delete-orphan",
        order_by="GiftCertificateTransaction.id",
    )


class GiftCertificateTransaction(Base):
    __tablename__ = "gift_certificate_transactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cert_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("gift_certificates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    sms_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sms_sent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sms_error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confirm_code: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GiftTransactionStatus.OPENED.value
    )

    certificate: Mapped[GiftCertificate] = relationship(back_populates="transactions")

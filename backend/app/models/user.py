import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    worker = "worker"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pin_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UserRole.user.value, index=True
    )
    # Список ключей прав для role=worker (см. app.permissions). У клиентов — [].
    admin_permissions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signup_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    interactions = relationship("Interaction", back_populates="user")
    signup_campaign = relationship("MarketingCampaign", foreign_keys=[signup_campaign_id])
    tag_weights = relationship("UserTagWeight", back_populates="user")
    tag_pair_weights = relationship("UserTagPairWeight", back_populates="user")

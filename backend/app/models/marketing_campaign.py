import re
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def normalize_campaign_slug(raw: str) -> str:
    s = raw.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("slug пустой")
    if not _SLUG_RE.match(s):
        raise ValueError(
            "slug: латиница, цифры, _ и -; от 1 до 63 символов, начинается с буквы или цифры",
        )
    return s


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(200), nullable=False, default="/")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    sessions = relationship("UserSession", back_populates="campaign")

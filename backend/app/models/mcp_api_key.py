import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

OWNER_SUPERUSER = "superuser"
OWNER_WORKER = "worker"
SCOPE_READ = "read"
SCOPE_WRITE = "write"


class McpApiKey(Base):
    """Долгоживущий ключ MCP закупок.

    У суперпользователя нет строки в users, поэтому его ключ хранится с
    user_id = NULL. Открытый текст ключа лежит в key_plain, чтобы админка
    могла показать его снова; при отзыве поле очищается.
    """

    __tablename__ = "mcp_api_keys"
    __table_args__ = (
        CheckConstraint(
            "(owner_role = 'superuser' AND user_id IS NULL) "
            "OR (owner_role = 'worker' AND user_id IS NOT NULL)",
            name="ck_mcp_api_keys_owner",
        ),
        CheckConstraint(
            "scope IN ('read', 'write')",
            name="ck_mcp_api_keys_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_role: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_tail: Mapped[str] = mapped_column(String(8), nullable=False)
    key_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default=SCOPE_READ)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

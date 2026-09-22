"""MCP keys for procurement tools

Revision ID: 051_mcp_api_keys
Revises: 050_ranking_eval
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "051_mcp_api_keys"
down_revision: Union[str, None] = "050_ranking_eval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_role", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_tail", sa.String(length=8), nullable=False),
        sa.Column("key_plain", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(owner_role = 'superuser' AND user_id IS NULL) "
            "OR (owner_role = 'worker' AND user_id IS NOT NULL)",
            name="ck_mcp_api_keys_owner",
        ),
        sa.CheckConstraint(
            "scope IN ('read', 'write')",
            name="ck_mcp_api_keys_scope",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash", name="uq_mcp_api_keys_key_hash"),
    )
    op.create_index("ix_mcp_api_keys_user_id", "mcp_api_keys", ["user_id"])
    op.create_index(
        "uq_mcp_api_keys_active_user",
        "mcp_api_keys",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL AND user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_mcp_api_keys_active_superuser",
        "mcp_api_keys",
        ["owner_role"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL AND owner_role = 'superuser'"),
    )


def downgrade() -> None:
    op.drop_index("uq_mcp_api_keys_active_superuser", table_name="mcp_api_keys")
    op.drop_index("uq_mcp_api_keys_active_user", table_name="mcp_api_keys")
    op.drop_index("ix_mcp_api_keys_user_id", table_name="mcp_api_keys")
    op.drop_table("mcp_api_keys")

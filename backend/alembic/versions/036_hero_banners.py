"""hero_banners for vogue home page

Revision ID: 036_hero_banners
Revises: 035_season_primary
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036_hero_banners"
down_revision: Union[str, None] = "035_season_primary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hero_banners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=120), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("image_url_desktop", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("link_label", sa.String(length=80), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.alter_column("hero_banners", "is_active", server_default=None)
    op.alter_column("hero_banners", "priority", server_default=None)


def downgrade() -> None:
    op.drop_table("hero_banners")

"""promo_banners + promo_banner_impressions

Revision ID: 020_promo_banners
Revises: 019_user_signup_campaign
Create Date: 2026-05-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020_promo_banners"
down_revision: Union[str, None] = "019_user_signup_campaign"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Тип создаём один раз в upgrade(); в create_table — create_type=False, иначе дубль CREATE TYPE.
_display_mode = postgresql.ENUM(
    "once",
    "twice",
    "every_visit",
    name="promo_banner_display_mode",
    create_type=False,
)


def upgrade() -> None:
    _display_mode.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "promo_banners",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("link_label", sa.String(length=80), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "display_mode",
            _display_mode,
            nullable=False,
            server_default="once",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "promo_banner_impressions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("banner_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["banner_id"], ["promo_banners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "banner_id",
            "session_id",
            name="uq_promo_banner_impression_banner_session",
        ),
        sa.UniqueConstraint(
            "banner_id",
            "user_id",
            name="uq_promo_banner_impression_banner_user",
        ),
    )
    op.create_index(
        "ix_promo_banner_impressions_banner_id",
        "promo_banner_impressions",
        ["banner_id"],
        unique=False,
    )
    op.create_index(
        "ix_promo_banner_impressions_session_id",
        "promo_banner_impressions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_promo_banner_impressions_user_id",
        "promo_banner_impressions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_promo_banner_impressions_user_id", table_name="promo_banner_impressions")
    op.drop_index("ix_promo_banner_impressions_session_id", table_name="promo_banner_impressions")
    op.drop_index("ix_promo_banner_impressions_banner_id", table_name="promo_banner_impressions")
    op.drop_table("promo_banner_impressions")
    op.drop_table("promo_banners")
    _display_mode.drop(op.get_bind(), checkfirst=True)

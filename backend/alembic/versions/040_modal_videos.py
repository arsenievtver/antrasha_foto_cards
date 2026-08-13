"""modal_videos library for in-app video modal

Revision ID: 040_modal_videos
Revises: 039_split_categories
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "040_modal_videos"
down_revision: Union[str, None] = "039_split_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "modal_videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(length=500), nullable=True),
        sa.Column("poster_url", sa.String(length=500), nullable=True),
        sa.Column("cta_mode", sa.String(length=20), nullable=False, server_default="close"),
        sa.Column("cta_label", sa.String(length=80), nullable=True),
        sa.Column("lead_note", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("slug", name="uq_modal_videos_slug"),
    )
    op.alter_column("modal_videos", "cta_mode", server_default=None)
    op.alter_column("modal_videos", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_table("modal_videos")

"""marketing_campaigns + sessions.campaign_id (ref attribution)

Revision ID: 018_marketing_campaigns
Revises: 017_photo_like_counters
Create Date: 2026-05-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_marketing_campaigns"
down_revision: Union[str, None] = "017_photo_like_counters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False, server_default="/"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_marketing_campaigns_slug", "marketing_campaigns", ["slug"], unique=True,
    )
    op.add_column(
        "sessions",
        sa.Column("campaign_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sessions_campaign_id",
        "sessions",
        "marketing_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sessions_campaign_id", "sessions", ["campaign_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sessions_campaign_id", table_name="sessions")
    op.drop_constraint("fk_sessions_campaign_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "campaign_id")
    op.drop_index("ix_marketing_campaigns_slug", table_name="marketing_campaigns")
    op.drop_table("marketing_campaigns")

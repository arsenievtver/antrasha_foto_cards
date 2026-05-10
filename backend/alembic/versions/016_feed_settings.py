"""singleton feed_settings: optional tagging gate for /feed

Revision ID: 016_feed_settings
Revises: 015_photo_tags_version
Create Date: 2026-05-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_feed_settings"
down_revision: Union[str, None] = "015_photo_tags_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feed_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "require_tagging_review_for_feed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO feed_settings (id, require_tagging_review_for_feed) VALUES (1, false)",
        ),
    )
    op.alter_column(
        "feed_settings",
        "require_tagging_review_for_feed",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_table("feed_settings")

"""photo tagging claim for worker queue

Revision ID: 004_tagging_claim
Revises: 003_yandex_only
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_tagging_claim"
down_revision: Union[str, None] = "003_yandex_only"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column(
            "tagging_claimed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "photos",
        sa.Column("tagging_claimed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_photos_tagging_claimed_by_id",
        "photos",
        ["tagging_claimed_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_photos_tagging_claimed_until",
        "photos",
        ["tagging_claimed_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_photos_tagging_claimed_until", table_name="photos")
    op.drop_index("ix_photos_tagging_claimed_by_id", table_name="photos")
    op.drop_column("photos", "tagging_claimed_until")
    op.drop_column("photos", "tagging_claimed_by_id")

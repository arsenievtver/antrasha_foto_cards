"""liked photos snapshot for fitting requests

Revision ID: 014_fitting_request_liked_photos
Revises: 013_fitting_requests
Create Date: 2026-05-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_fitting_request_liked_photos"
down_revision: Union[str, None] = "013_fitting_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fitting_request_liked_photos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fitting_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("photos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("photo_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_fitting_request_liked_photos_request_id",
        "fitting_request_liked_photos",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_fitting_request_liked_photos_photo_id",
        "fitting_request_liked_photos",
        ["photo_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fitting_request_liked_photos_photo_id", table_name="fitting_request_liked_photos")
    op.drop_index("ix_fitting_request_liked_photos_request_id", table_name="fitting_request_liked_photos")
    op.drop_table("fitting_request_liked_photos")

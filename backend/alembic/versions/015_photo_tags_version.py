"""photos.tags_version for optimistic locking on tag saves

Revision ID: 015_photo_tags_version
Revises: 014_fitting_request_liked_photos
Create Date: 2026-05-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_photo_tags_version"
down_revision: Union[str, None] = "014_fitting_request_liked_photos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("tags_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("photos", "tags_version", server_default=None)


def downgrade() -> None:
    op.drop_column("photos", "tags_version")

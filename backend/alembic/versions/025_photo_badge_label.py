"""photos.badge_label for sale / promo card badge

Revision ID: 025_photo_badge_label
Revises: 024_rename_person_image_key
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025_photo_badge_label"
down_revision: Union[str, None] = "024_rename_person_image_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("badge_label", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("photos", "badge_label")

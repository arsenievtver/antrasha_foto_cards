"""photos.moy_sklad_id for MoySklad / inventory linkage

Revision ID: 012_moy_sklad
Revises: 011_brands
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_moy_sklad"
down_revision: Union[str, None] = "011_brands"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("moy_sklad_id", sa.String(128), nullable=True),
    )
    op.create_index("ix_photos_moy_sklad_id", "photos", ["moy_sklad_id"])


def downgrade() -> None:
    op.drop_index("ix_photos_moy_sklad_id", table_name="photos")
    op.drop_column("photos", "moy_sklad_id")

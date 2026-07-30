"""add season is_primary for PWA dashboard

Revision ID: 035_season_primary
Revises: 034_cat_norm
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_season_primary"
down_revision: Union[str, None] = "034_cat_norm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seasons",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Partial unique: at most one primary season.
    op.create_index(
        "uq_seasons_one_primary",
        "seasons",
        ["is_primary"],
        unique=True,
        postgresql_where=sa.text("is_primary IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_seasons_one_primary", table_name="seasons")
    op.drop_column("seasons", "is_primary")

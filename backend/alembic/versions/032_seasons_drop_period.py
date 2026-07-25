"""seasons: drop starts_on / ends_on — season is a label, not a calendar window

Revision ID: 032_seasons_drop_period
Revises: 031_fx_rates_period
Create Date: 2026-07-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "032_seasons_drop_period"
down_revision: Union[str, None] = "031_fx_rates_period"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("seasons")}
    if "ends_on" in cols:
        op.drop_column("seasons", "ends_on")
    if "starts_on" in cols:
        op.drop_column("seasons", "starts_on")


def downgrade() -> None:
    op.add_column("seasons", sa.Column("starts_on", sa.Date(), nullable=True))
    op.add_column("seasons", sa.Column("ends_on", sa.Date(), nullable=True))

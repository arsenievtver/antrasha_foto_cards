"""fx_rates: period valid_from/valid_to instead of single rate_date

Revision ID: 031_fx_rates_period
Revises: 030_procurement_foundation
Create Date: 2026-07-25

Для БД, где уже накатана 030 со столбцом rate_date: переносим в период
(valid_from = rate_date, valid_to = rate_date — однодневный период).
Если 030 уже создала valid_from (свежая правка) — миграция no-op.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "031_fx_rates_period"
down_revision: Union[str, None] = "030_procurement_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("fx_rates")}
    if "valid_from" in cols and "rate_date" not in cols:
        # Свежая 030 уже с периодом — ничего не делаем.
        return

    if "valid_from" not in cols:
        op.add_column("fx_rates", sa.Column("valid_from", sa.Date(), nullable=True))
        op.add_column("fx_rates", sa.Column("valid_to", sa.Date(), nullable=True))

    if "rate_date" in cols:
        op.execute(
            sa.text(
                "UPDATE fx_rates SET valid_from = rate_date, "
                "valid_to = rate_date WHERE valid_from IS NULL"
            )
        )

    op.alter_column("fx_rates", "valid_from", nullable=False)

    if "rate_date" in cols:
        op.drop_index("ix_fx_rates_rate_date", table_name="fx_rates")
        op.drop_constraint("fx_rates_rate_date_key", "fx_rates", type_="unique")
        op.drop_column("fx_rates", "rate_date")

    existing = {ix["name"] for ix in inspect(bind).get_indexes("fx_rates")}
    if "ix_fx_rates_valid_from" not in existing:
        op.create_index("ix_fx_rates_valid_from", "fx_rates", ["valid_from"])
    if "ix_fx_rates_valid_to" not in existing:
        op.create_index("ix_fx_rates_valid_to", "fx_rates", ["valid_to"])


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("fx_rates")}
    if "rate_date" in cols:
        return

    op.add_column("fx_rates", sa.Column("rate_date", sa.Date(), nullable=True))
    op.execute(sa.text("UPDATE fx_rates SET rate_date = valid_from"))
    op.alter_column("fx_rates", "rate_date", nullable=False)
    op.create_index("ix_fx_rates_rate_date", "fx_rates", ["rate_date"], unique=True)
    op.create_unique_constraint("fx_rates_rate_date_key", "fx_rates", ["rate_date"])

    op.drop_index("ix_fx_rates_valid_to", table_name="fx_rates")
    op.drop_index("ix_fx_rates_valid_from", table_name="fx_rates")
    op.drop_column("fx_rates", "valid_to")
    op.drop_column("fx_rates", "valid_from")

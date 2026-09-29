"""fill missing EUR/RUB rate on payments and shipments from fx_rates

Revision ID: 057_fill_missing_doc_rates
Revises: 056_single_order_per_season
Create Date: 2026-09-29

Документы, сохранённые до появления периода курса в справочнике, остались
без курса и без суммы в рублях. Подставляем курс периода на дату документа.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "057_fill_missing_doc_rates"
down_revision: Union[str, None] = "056_single_order_per_season"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fill(table: str, date_column: str) -> None:
    op.execute(
        f"""
        UPDATE {table} AS d
        SET eur_rub_rate = r.eur_rub,
            amount_rub = ROUND(d.amount_eur * r.eur_rub, 2)
        FROM fx_rates AS r
        WHERE d.eur_rub_rate IS NULL
          AND r.valid_from <= d.{date_column}
          AND (r.valid_to IS NULL OR r.valid_to >= d.{date_column})
        """
    )


def upgrade() -> None:
    _fill("payments", "paid_on")
    _fill("shipments", "shipped_on")


def downgrade() -> None:
    pass

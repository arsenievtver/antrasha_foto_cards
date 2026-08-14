"""allow multiple seasons on PWA dashboard

Revision ID: 042_seasons_multi_pwa
Revises: 041_split_accessories
Create Date: 2026-08-14

Снимаем partial unique на is_primary: на дашборде PWA можно показывать
несколько сезонов (обычно текущий и следующий). Порядок — sort_order.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042_seasons_multi_pwa"
down_revision: Union[str, None] = "041_split_accessories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_seasons_one_primary", table_name="seasons")


def downgrade() -> None:
    # Перед восстановлением unique оставляем только один primary
    # (с наибольшим sort_order), остальные снимаем.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           ORDER BY sort_order DESC, created_at DESC
                       ) AS rn
                FROM seasons
                WHERE is_primary IS TRUE
            )
            UPDATE seasons
            SET is_primary = FALSE
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )
    op.create_index(
        "uq_seasons_one_primary",
        "seasons",
        ["is_primary"],
        unique=True,
        postgresql_where=sa.text("is_primary IS TRUE"),
    )

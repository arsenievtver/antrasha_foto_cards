"""add season is_order_plan for order guidance

Revision ID: 043_season_order_plan
Revises: 042_seasons_multi_pwa
Create Date: 2026-08-14

Один сезон владеет разделом «Для заказа» и планами категорий.
Seed: Весна-Лето 2027 / ВЛ2027.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043_season_order_plan"
down_revision: Union[str, None] = "042_seasons_multi_pwa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seasons",
        sa.Column(
            "is_order_plan",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "uq_seasons_one_order_plan",
        "seasons",
        ["is_order_plan"],
        unique=True,
        postgresql_where=sa.text("is_order_plan IS TRUE"),
    )
    op.execute(
        sa.text(
            """
            UPDATE seasons
            SET is_order_plan = TRUE
            WHERE id = (
                SELECT id FROM seasons
                WHERE code ILIKE '%ВЛ2027%'
                   OR name ILIKE '%весна%лето%2027%'
                ORDER BY sort_order DESC, created_at DESC
                LIMIT 1
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_seasons_one_order_plan", table_name="seasons")
    op.drop_column("seasons", "is_order_plan")

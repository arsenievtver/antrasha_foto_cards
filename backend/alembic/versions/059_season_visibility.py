"""season visibility slots: previous, current, next

Revision ID: 059_season_visibility
Revises: 058_staff_feedback
Create Date: 2026-09-30

Три роли видимости сезона. Каждая роль не больше чем у одного сезона.
Дашборд читает current и next. Галочки проставляет админка после выкладки.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "059_season_visibility"
down_revision: Union[str, None] = "058_staff_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("seasons", sa.Column("visibility", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_seasons_visibility",
        "seasons",
        "visibility IS NULL OR visibility IN ('previous', 'current', 'next')",
    )
    op.create_index(
        "uq_seasons_visibility",
        "seasons",
        ["visibility"],
        unique=True,
        postgresql_where=sa.text("visibility IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_seasons_visibility", table_name="seasons")
    op.drop_constraint("ck_seasons_visibility", "seasons", type_="check")
    op.drop_column("seasons", "visibility")

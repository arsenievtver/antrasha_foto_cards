"""add users.admin_permissions for worker ACL

Revision ID: 033_worker_admin_permissions
Revises: 032_seasons_drop_period
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033_worker_admin_permissions"
down_revision: Union[str, None] = "032_seasons_drop_period"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "admin_permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    # Существующие сотрудники сохраняют текущий доступ (раздел Фото).
    op.execute(
        """
        UPDATE users
        SET admin_permissions = '["photos"]'::jsonb
        WHERE role = 'worker'
        """
    )


def downgrade() -> None:
    op.drop_column("users", "admin_permissions")

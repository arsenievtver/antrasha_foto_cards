"""user display_name for app registration

Revision ID: 008_user_display_name
Revises: 007_ai_ingest
Create Date: 2026-05-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_user_display_name"
down_revision: Union[str, None] = "007_ai_ingest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")

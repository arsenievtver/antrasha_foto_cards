"""push_subscriptions.gender_scope

Revision ID: 022_push_gender_scope
Revises: 021_push_subscriptions
Create Date: 2026-06-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022_push_gender_scope"
down_revision: Union[str, None] = "021_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "push_subscriptions",
        sa.Column(
            "gender_scope",
            sa.String(length=10),
            nullable=False,
            server_default="both",
        ),
    )
    op.alter_column("push_subscriptions", "gender_scope", server_default=None)


def downgrade() -> None:
    op.drop_column("push_subscriptions", "gender_scope")

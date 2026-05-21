"""users.signup_campaign_id — атрибуция регистрации к рекламной ссылке

Revision ID: 019_user_signup_campaign
Revises: 018_marketing_campaigns
Create Date: 2026-05-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_user_signup_campaign"
down_revision: Union[str, None] = "018_marketing_campaigns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("signup_campaign_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_signup_campaign_id",
        "users",
        "marketing_campaigns",
        ["signup_campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_users_signup_campaign_id", "users", ["signup_campaign_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_signup_campaign_id", table_name="users")
    op.drop_constraint("fk_users_signup_campaign_id", "users", type_="foreignkey")
    op.drop_column("users", "signup_campaign_id")

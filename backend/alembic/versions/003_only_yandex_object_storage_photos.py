"""remove non-Object Storage demo photos; default source_type yc_object_storage

Revision ID: 003_yandex_only
Revises: 002_user_role
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_yandex_only"
down_revision: Union[str, None] = "002_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем демо (picsum и любые записи не из синхронизации бакетов).
    op.execute(sa.text("DELETE FROM photos WHERE source_type <> 'yc_object_storage'"))
    op.alter_column(
        "photos",
        "source_type",
        server_default=sa.text("'yc_object_storage'"),
        existing_type=sa.String(length=20),
        existing_nullable=False,
        existing_server_default=sa.text("'original'"),
    )


def downgrade() -> None:
    op.alter_column(
        "photos",
        "source_type",
        server_default=sa.text("'original'"),
        existing_type=sa.String(length=20),
        existing_nullable=False,
        existing_server_default=sa.text("'yc_object_storage'"),
    )

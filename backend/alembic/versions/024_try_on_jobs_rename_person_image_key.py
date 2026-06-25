"""rename person_image_key to person_image_path in try_on_jobs

Revision ID: 024_try_on_jobs_rename_person_image_key
Revises: 023_try_on_jobs
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "024_rename_person_image_key"
down_revision: Union[str, None] = "023_try_on_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("try_on_jobs", "person_image_key", new_column_name="person_image_path")


def downgrade() -> None:
    op.alter_column("try_on_jobs", "person_image_path", new_column_name="person_image_key")
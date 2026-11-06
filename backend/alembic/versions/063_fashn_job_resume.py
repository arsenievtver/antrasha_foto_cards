"""fashn job id and stage: resume paid generations instead of resubmitting

Revision ID: 063_fashn_job_resume
Revises: 062_outlet_photo_jobs
Create Date: 2026-11-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063_fashn_job_resume"
down_revision: Union[str, None] = "062_outlet_photo_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_ingest_jobs", sa.Column("fashn_job_id", sa.Text(), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("stage", sa.String(length=20), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("stage_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outlet_photo_jobs", sa.Column("fashn_job_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("outlet_photo_jobs", "fashn_job_id")
    op.drop_column("ai_ingest_jobs", "stage_at")
    op.drop_column("ai_ingest_jobs", "stage")
    op.drop_column("ai_ingest_jobs", "fashn_job_id")

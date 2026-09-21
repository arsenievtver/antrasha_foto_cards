"""user_taste_vectors.collection_gender + feed_settings.taste_vectors_separate_by_gender

Revision ID: 049_taste_by_gender
Revises: 048_ai_ingest_photo
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049_taste_by_gender"
down_revision: Union[str, None] = "048_ai_ingest_photo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_taste_vectors",
        sa.Column("collection_gender", sa.String(length=10), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_taste_vectors_gender",
        "user_taste_vectors",
        "collection_gender IS NULL OR collection_gender IN ('male', 'female')",
    )

    op.drop_index("uq_user_taste_vectors_user", table_name="user_taste_vectors")
    op.drop_index("uq_user_taste_vectors_session", table_name="user_taste_vectors")

    # Legacy unified row → male + female copy (same embedding) when embedding exists.
    op.execute(
        sa.text(
            """
            INSERT INTO user_taste_vectors (
                id, user_id, session_id, model_version, embedding, swipe_updates,
                updated_at, collection_gender
            )
            SELECT
                gen_random_uuid(), user_id, session_id, model_version, embedding,
                swipe_updates, updated_at, 'female'
            FROM user_taste_vectors
            WHERE collection_gender IS NULL AND embedding IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE user_taste_vectors
            SET collection_gender = 'male'
            WHERE collection_gender IS NULL
            """
        )
    )

    op.create_index(
        "uq_user_taste_vectors_user_gender",
        "user_taste_vectors",
        ["user_id", "collection_gender"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND collection_gender IS NOT NULL"),
    )
    op.create_index(
        "uq_user_taste_vectors_user_unified",
        "user_taste_vectors",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND collection_gender IS NULL"),
    )
    op.create_index(
        "uq_user_taste_vectors_session_gender",
        "user_taste_vectors",
        ["session_id", "collection_gender"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL AND collection_gender IS NOT NULL"),
    )
    op.create_index(
        "uq_user_taste_vectors_session_unified",
        "user_taste_vectors",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL AND collection_gender IS NULL"),
    )

    op.add_column(
        "feed_settings",
        sa.Column(
            "taste_vectors_separate_by_gender",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("feed_settings", "taste_vectors_separate_by_gender")

    op.drop_index("uq_user_taste_vectors_session_unified", table_name="user_taste_vectors")
    op.drop_index("uq_user_taste_vectors_session_gender", table_name="user_taste_vectors")
    op.drop_index("uq_user_taste_vectors_user_unified", table_name="user_taste_vectors")
    op.drop_index("uq_user_taste_vectors_user_gender", table_name="user_taste_vectors")

    op.execute(
        sa.text(
            """
            DELETE FROM user_taste_vectors a
            USING user_taste_vectors b
            WHERE a.collection_gender = 'female'
              AND b.collection_gender = 'male'
              AND a.user_id IS NOT DISTINCT FROM b.user_id
              AND a.session_id IS NOT DISTINCT FROM b.session_id
              AND a.embedding IS NOT DISTINCT FROM b.embedding
            """
        )
    )
    op.execute(sa.text("UPDATE user_taste_vectors SET collection_gender = NULL"))
    op.drop_constraint("ck_user_taste_vectors_gender", "user_taste_vectors", type_="check")
    op.drop_column("user_taste_vectors", "collection_gender")

    op.create_index(
        "uq_user_taste_vectors_user",
        "user_taste_vectors",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_user_taste_vectors_session",
        "user_taste_vectors",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )

"""pgvector: photo_embeddings, user_taste_vectors, feed ranking mode

Revision ID: 046_vector_taste
Revises: 045_xfashion_landing
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046_vector_taste"
down_revision: Union[str, None] = "045_xfashion_landing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 512


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.execute(
        sa.text(
            f"""
            CREATE TABLE photo_embeddings (
                photo_id UUID PRIMARY KEY
                    REFERENCES photos(id) ON DELETE CASCADE,
                model_version VARCHAR(64) NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE TABLE user_taste_vectors (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                model_version VARCHAR(64) NOT NULL,
                embedding vector({EMBEDDING_DIM}),
                swipe_updates INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT ck_user_taste_vectors_owner CHECK (
                    (user_id IS NOT NULL AND session_id IS NULL) OR
                    (user_id IS NULL AND session_id IS NOT NULL)
                )
            )
            """
        )
    )

    op.create_index("ix_user_taste_vectors_user_id", "user_taste_vectors", ["user_id"])
    op.create_index("ix_user_taste_vectors_session_id", "user_taste_vectors", ["session_id"])
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

    op.add_column(
        "feed_settings",
        sa.Column(
            "feed_ranking_mode",
            sa.String(length=16),
            nullable=False,
            server_default="tags",
        ),
    )
    op.add_column(
        "feed_settings",
        sa.Column(
            "feed_vector_weight",
            sa.Float(),
            nullable=False,
            server_default="0.65",
        ),
    )


def downgrade() -> None:
    op.drop_column("feed_settings", "feed_vector_weight")
    op.drop_column("feed_settings", "feed_ranking_mode")
    op.drop_index("uq_user_taste_vectors_session", table_name="user_taste_vectors")
    op.drop_index("uq_user_taste_vectors_user", table_name="user_taste_vectors")
    op.drop_index("ix_user_taste_vectors_session_id", table_name="user_taste_vectors")
    op.drop_index("ix_user_taste_vectors_user_id", table_name="user_taste_vectors")
    op.drop_table("user_taste_vectors")
    op.drop_table("photo_embeddings")
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector"))

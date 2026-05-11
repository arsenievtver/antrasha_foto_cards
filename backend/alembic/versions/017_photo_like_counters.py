"""photos.likes_count / dislikes_count + backfill (per-identity dedupe)

Revision ID: 017_photo_like_counters
Revises: 016_feed_settings
Create Date: 2026-05-11

Денормализованные счётчики реакций на фото:
- likes_count, dislikes_count считают уникальные «идентичности» (user_id ИЛИ session_id).
- Backfill использует «последний вердикт»: если идентичность сначала лайкнула, потом
  дизлайкнула — учитывается только последнее действие (по created_at).
- Поддерживаются в актуальном состоянии в routers/interactions.create_interaction.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_photo_like_counters"
down_revision: Union[str, None] = "016_feed_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("likes_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "photos",
        sa.Column("dislikes_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill: для каждой пары (photo_id, identity) берём ПОСЛЕДНЕЕ like/dislike по created_at.
    # identity = user_id::text, если пользователь зарегистрирован, иначе 'sess:' + session_id::text.
    # Это гарантирует, что повторные свайпы одной и той же идентичности не учтены,
    # а «переключение» (like → dislike) корректно засчитано в текущую сторону.
    op.execute(
        sa.text(
            """
            WITH latest AS (
                SELECT DISTINCT ON (photo_id, identity)
                       photo_id,
                       identity,
                       action
                FROM (
                    SELECT
                        photo_id,
                        COALESCE(user_id::text, 'sess:' || session_id::text) AS identity,
                        action,
                        created_at
                    FROM interactions
                    WHERE action IN ('like', 'dislike')
                ) i
                ORDER BY photo_id, identity, created_at DESC
            ),
            agg AS (
                SELECT
                    photo_id,
                    COUNT(*) FILTER (WHERE action = 'like') AS likes,
                    COUNT(*) FILTER (WHERE action = 'dislike') AS dislikes
                FROM latest
                GROUP BY photo_id
            )
            UPDATE photos p
            SET likes_count = COALESCE(agg.likes, 0),
                dislikes_count = COALESCE(agg.dislikes, 0)
            FROM agg
            WHERE p.id = agg.photo_id
            """,
        ),
    )

    op.alter_column("photos", "likes_count", server_default=None)
    op.alter_column("photos", "dislikes_count", server_default=None)


def downgrade() -> None:
    op.drop_column("photos", "dislikes_count")
    op.drop_column("photos", "likes_count")

"""tag groups, catalog constraints, worker tagging fields on photos

Revision ID: 005_tag_groups
Revises: 004_tagging_claim
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_tag_groups"
down_revision: Union[str, None] = "004_tagging_claim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Старые теги без группы — привязываем к этой группе до seed каталога
LEGACY_GROUP_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.create_table(
        "tag_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("section", sa.String(80), nullable=False),
        sa.Column("section_sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_tags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tags", sa.Integer(), nullable=False, server_default="99"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tag_groups_slug", "tag_groups", ["slug"], unique=True)
    op.create_index("ix_tag_groups_section", "tag_groups", ["section"], unique=False)

    op.execute(
        sa.text(
            f"""
            INSERT INTO tag_groups (id, slug, title, section, section_sort, group_sort, min_tags, max_tags)
            VALUES ('{LEGACY_GROUP_ID}'::uuid, 'legacy', 'Устаревшие теги', 'legacy', 999, 0, 0, 99)
            """
        )
    )

    op.add_column(
        "tags",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("tags", sa.Column("subgroup_key", sa.String(50), nullable=True))
    op.add_column("tags", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tags", sa.Column("recommendation_weight", sa.Integer(), nullable=False, server_default="50"))
    op.add_column(
        "tags",
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        sa.text(f"UPDATE tags SET group_id = '{LEGACY_GROUP_ID}'::uuid WHERE group_id IS NULL"),
    )

    op.alter_column("tags", "group_id", nullable=False)

    op.drop_index("ix_tags_name", table_name="tags")

    op.create_foreign_key("fk_tags_group_id", "tags", "tag_groups", ["group_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key(
        "fk_tags_created_by_user_id",
        "tags",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("ix_tags_group_id", "tags", ["group_id"], unique=False)
    op.create_unique_constraint("uq_tags_group_id_name", "tags", ["group_id", "name"])

    op.add_column(
        "photos",
        sa.Column(
            "tagging_review_done",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "photos",
        sa.Column("tagging_uncertain", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("photos", sa.Column("worker_signal_love", sa.Boolean(), nullable=True))
    op.add_column("photos", sa.Column("worker_signal_hit", sa.Boolean(), nullable=True))
    op.add_column("photos", sa.Column("worker_signal_hard", sa.Boolean(), nullable=True))
    op.add_column("photos", sa.Column("brand", sa.String(200), nullable=True))
    op.add_column("photos", sa.Column("price_segment", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("photos", "price_segment")
    op.drop_column("photos", "tagging_review_done")
    op.drop_column("photos", "brand")
    op.drop_column("photos", "worker_signal_hard")
    op.drop_column("photos", "worker_signal_hit")
    op.drop_column("photos", "worker_signal_love")
    op.drop_column("photos", "tagging_uncertain")

    op.drop_constraint("uq_tags_group_id_name", "tags", type_="unique")
    op.drop_index("ix_tags_group_id", table_name="tags")
    op.drop_constraint("fk_tags_created_by_user_id", "tags", type_="foreignkey")
    op.drop_constraint("fk_tags_group_id", "tags", type_="foreignkey")

    op.drop_column("tags", "created_by_user_id")
    op.drop_column("tags", "recommendation_weight")
    op.drop_column("tags", "sort_order")
    op.drop_column("tags", "subgroup_key")
    op.drop_column("tags", "group_id")

    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    op.drop_index("ix_tag_groups_section", table_name="tag_groups")
    op.drop_index("ix_tag_groups_slug", table_name="tag_groups")
    op.drop_table("tag_groups")

"""split pants/shorts and dresses/skirts categories

Revision ID: 039_split_categories
Revises: 038_outlet_photo_uploads
Create Date: 2026-08-05

Зеркалим сплит групп в МойСклад:
- брюки/джинсы отделены от бриджей/шорт (муж и жен);
- платья отделены от юбок (старый uuid = Юбки, новый = Платья).
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_split_categories"
down_revision: Union[str, None] = "038_outlet_photo_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RENAMES = {
    "46b4f0d3-5708-11e9-9ff4-315000d079ad": "Брюки, джинсы муж",
    "78fabba1-9e44-11e9-9ff4-31500007d6c1": "Брюки, джинсы жен",
    "26114fa1-a495-11e9-9ff4-3150000fa9a1": "Юбки жен",
}

# (moy_sklad_id, name, gender, path_name, after_ms_id)
NEW_CATEGORIES = [
    (
        "55edd126-8bff-11f1-0a80-142f000aee50",
        "Бриджи, шорты муж",
        "men",
        "Мужская коллекция",
        "46b4f0d3-5708-11e9-9ff4-315000d079ad",
    ),
    (
        "4643b20e-8bfa-11f1-0a80-18830009f9ac",
        "Бриджи, шорты жен",
        "women",
        "Женская коллекция",
        "78fabba1-9e44-11e9-9ff4-31500007d6c1",
    ),
    (
        "65dca14b-8bfd-11f1-0a80-0fbf000a6721",
        "Платья жен",
        "women",
        "Женская коллекция",
        "26114fa1-a495-11e9-9ff4-3150000fa9a1",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    for ms_id, name in RENAMES.items():
        bind.execute(
            sa.text(
                """
                UPDATE categories
                SET name = :name, is_active = true
                WHERE moy_sklad_id = :ms_id
                """
            ),
            {"ms_id": ms_id, "name": name},
        )

    for ms_id, name, gender, path_name, after_ms_id in NEW_CATEGORIES:
        exists = bind.execute(
            sa.text("SELECT 1 FROM categories WHERE moy_sklad_id = :ms_id"),
            {"ms_id": ms_id},
        ).scalar()
        if exists:
            bind.execute(
                sa.text(
                    """
                    UPDATE categories
                    SET name = :name,
                        gender = :gender,
                        path_name = :path_name,
                        is_active = true
                    WHERE moy_sklad_id = :ms_id
                    """
                ),
                {
                    "ms_id": ms_id,
                    "name": name,
                    "gender": gender,
                    "path_name": path_name,
                },
            )
            continue

        sibling_sort = bind.execute(
            sa.text(
                "SELECT sort_order FROM categories WHERE moy_sklad_id = :ms_id"
            ),
            {"ms_id": after_ms_id},
        ).scalar()
        sort_order = (sibling_sort or 0) + 1

        # Платья ставим перед Юбками (after_ms_id указывает на юбки).
        if ms_id == "65dca14b-8bfd-11f1-0a80-0fbf000a6721":
            sort_order = sibling_sort or 0
            bind.execute(
                sa.text(
                    """
                    UPDATE categories
                    SET sort_order = sort_order + 1
                    WHERE moy_sklad_id = :skirts_ms_id
                    """
                ),
                {"skirts_ms_id": after_ms_id},
            )

        bind.execute(
            sa.text(
                """
                INSERT INTO categories (
                    id, name, gender, moy_sklad_id, path_name,
                    is_active, sort_order, created_at
                )
                VALUES (
                    :id, :name, :gender, :ms_id, :path_name,
                    true, :sort_order, now()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "gender": gender,
                "ms_id": ms_id,
                "path_name": path_name,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM categories
            WHERE moy_sklad_id IN :ms_ids
            """
        ).bindparams(sa.bindparam("ms_ids", expanding=True)),
        {"ms_ids": [row[0] for row in NEW_CATEGORIES]},
    )

    revert = {
        "46b4f0d3-5708-11e9-9ff4-315000d079ad": "Брюки, джинсы, бриджи, шорты муж",
        "78fabba1-9e44-11e9-9ff4-31500007d6c1": "Брюки, джинсы, бриджи, шорты жен",
        "26114fa1-a495-11e9-9ff4-3150000fa9a1": "Платья, юбки жен",
    }
    for ms_id, name in revert.items():
        bind.execute(
            sa.text(
                """
                UPDATE categories
                SET name = :name
                WHERE moy_sklad_id = :ms_id
                """
            ),
            {"ms_id": ms_id, "name": name},
        )

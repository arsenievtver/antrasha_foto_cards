"""normalize procurement categories to canonical names

Revision ID: 034_procurement_category_normalization
Revises: 033_worker_admin_permissions
Create Date: 2026-07-29

Приводим закупочные категории к канонической схеме:
- женские дубли сливаем в канонические категории;
- существующие строки заказов переводим на канонические category_id;
- фронту и API оставляем единые названия категорий.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_procurement_category_normalization"
down_revision: Union[str, None] = "033_worker_admin_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CANONICAL_NAMES = {
    "797d0e35-9e44-11e9-9ff4-31500007d733": "Рубашки",
    "79292943-9e44-11e9-9ff4-31500007d6f3": "Пиджаки, жакеты, бомбер жен",
    "21e1d207-b53f-11e9-9ff4-31500015315b": "Блузки, рубашки жен",
    "78fabba1-9e44-11e9-9ff4-31500007d6c1": "Брюки, джинсы, бриджи, шорты жен",
    "26114fa1-a495-11e9-9ff4-3150000fa9a1": "Платья, юбки жен",
}

ALIASES = {
    "463e7bec-34dd-11f1-0a80-148d00118078": "79292943-9e44-11e9-9ff4-31500007d6f3",
    "8ade28c6-6e3e-11f1-0a80-00b0001171b1": "78fabba1-9e44-11e9-9ff4-31500007d6c1",
}


def upgrade() -> None:
    bind = op.get_bind()

    for alias_ms_id, canonical_ms_id in ALIASES.items():
        bind.execute(
            sa.text(
                """
                UPDATE brand_order_category_lines AS lines
                SET category_id = canonical.id
                FROM categories AS alias
                JOIN categories AS canonical
                  ON canonical.moy_sklad_id = :canonical_ms_id
                WHERE alias.moy_sklad_id = :alias_ms_id
                  AND lines.category_id = alias.id
                """
            ),
            {"alias_ms_id": alias_ms_id, "canonical_ms_id": canonical_ms_id},
        )

    for ms_id, name in CANONICAL_NAMES.items():
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

    bind.execute(
        sa.text(
            """
            UPDATE categories
            SET is_active = false
            WHERE moy_sklad_id IN :alias_ids
            """
        ).bindparams(sa.bindparam("alias_ids", expanding=True)),
        {"alias_ids": list(ALIASES)},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE categories
            SET is_active = true
            WHERE moy_sklad_id IN :alias_ids
            """
        ).bindparams(sa.bindparam("alias_ids", expanding=True)),
        {"alias_ids": list(ALIASES)},
    )

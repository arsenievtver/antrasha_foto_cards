"""procurement: seasons, categories, brand orders, payments, shipments, fx rates

Revision ID: 030_procurement_foundation
Revises: 029_ai_ingest_source_mode
Create Date: 2026-07-25

Категории — зеркало групп товаров МойСклад, только ветки «Мужская коллекция»,
«Женская коллекция» и корневая «Аксессуары». Ветки Онлайн / Товар ТО / РАДУГА /
Нижнее белье в закупках не участвуют. Из женских дублей взяты варианты без
суффикса «жен»: «Пиджаки, жакеты, бомбер» и «Брюки, джинсы, бриджи, шорты».

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030_procurement_foundation"
down_revision: Union[str, None] = "029_ai_ingest_source_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (moy_sklad_id, name, gender, path_name)
SEED_CATEGORIES: list[tuple[str, str, str, str]] = [
    (
        "46b4f0d3-5708-11e9-9ff4-315000d079ad",
        "Брюки, джинсы, бриджи, шорты муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "46a5c5b7-5708-11e9-9ff4-315000d0798d",
        "Футболки, поло муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "797d0e35-9e44-11e9-9ff4-31500007d733",
        "Рубашки",
        "men",
        "Мужская коллекция",
    ),
    (
        "009bd151-b37b-11e9-9ff4-3150003a1bb1",
        "Пиджаки, жакеты, бомбер муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "7958c78e-9e44-11e9-9ff4-31500007d713",
        "Трикотаж муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "0ebca617-f97a-11e9-0a80-0579004f6022",
        "Верхняя одежда муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "eec41100-9847-11eb-0a80-0616000ac009",
        "Костюмы муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "f8fae156-b37a-11e9-9ff4-3150003a11ec",
        "Обувь муж",
        "men",
        "Мужская коллекция",
    ),
    (
        "8ade28c6-6e3e-11f1-0a80-00b0001171b1",
        "Брюки, джинсы, бриджи, шорты",
        "women",
        "Женская коллекция",
    ),
    (
        "f7b6946e-b37a-11e9-9ff4-3150003a0ff5",
        "Футболки, поло, топы жен",
        "women",
        "Женская коллекция",
    ),
    (
        "21e1d207-b53f-11e9-9ff4-31500015315b",
        "Блузки, рубашки",
        "women",
        "Женская коллекция",
    ),
    (
        "26114fa1-a495-11e9-9ff4-3150000fa9a1",
        "Платья, юбки",
        "women",
        "Женская коллекция",
    ),
    (
        "463e7bec-34dd-11f1-0a80-148d00118078",
        "Пиджаки, жакеты, бомбер",
        "women",
        "Женская коллекция",
    ),
    (
        "cd27a401-d3a6-11e9-0a80-02690003e199",
        "Трикотаж жен",
        "women",
        "Женская коллекция",
    ),
    (
        "0dea4445-f97a-11e9-0a80-0579004f5ecf",
        "Верхняя одежда жен",
        "women",
        "Женская коллекция",
    ),
    (
        "79419e87-9e44-11e9-9ff4-31500007d6fe",
        "Обувь жен",
        "women",
        "Женская коллекция",
    ),
    (
        "82adf299-8e8b-11e9-9ff4-31500007fc47",
        "Аксессуары",
        "unisex",
        "",
    ),
]


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_seasons_name", "seasons", ["name"], unique=True)
    op.create_index("ix_seasons_code", "seasons", ["code"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=False),
        sa.Column("moy_sklad_id", sa.String(length=64), nullable=True),
        sa.Column("path_name", sa.String(length=300), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("moy_sklad_id"),
    )
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)
    op.create_index("ix_categories_gender", "categories", ["gender"], unique=False)
    op.create_index(
        "ix_categories_moy_sklad_id", "categories", ["moy_sklad_id"], unique=True
    )

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("eur_rub", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fx_rates_valid_from", "fx_rates", ["valid_from"], unique=False)
    op.create_index("ix_fx_rates_valid_to", "fx_rates", ["valid_to"], unique=False)

    op.create_table(
        "brand_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("season_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("ordered_on", sa.Date(), nullable=True),
        sa.Column(
            "amount_eur",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("eur_rub_rate", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column(
            "has_prepayment", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "prepayment_amount_eur", sa.Numeric(precision=14, scale=2), nullable=True
        ),
        sa.Column("prepayment_due_on", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brand_orders_season_id", "brand_orders", ["season_id"])
    op.create_index("ix_brand_orders_brand_id", "brand_orders", ["brand_id"])

    op.create_table(
        "brand_order_category_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column(
            "amount_eur",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["brand_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_brand_order_category_lines_order_id",
        "brand_order_category_lines",
        ["order_id"],
    )
    op.create_index(
        "ix_brand_order_category_lines_category_id",
        "brand_order_category_lines",
        ["category_id"],
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("season_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="main"),
        sa.Column("amount_eur", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("eur_rub_rate", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("amount_rub", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["brand_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_season_id", "payments", ["season_id"])
    op.create_index("ix_payments_brand_id", "payments", ["brand_id"])
    op.create_index("ix_payments_paid_on", "payments", ["paid_on"])
    op.create_index("ix_payments_kind", "payments", ["kind"])

    op.create_table(
        "shipments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("season_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("shipped_on", sa.Date(), nullable=False),
        sa.Column("amount_eur", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("eur_rub_rate", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("amount_rub", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["brand_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
    op.create_index("ix_shipments_season_id", "shipments", ["season_id"])
    op.create_index("ix_shipments_brand_id", "shipments", ["brand_id"])
    op.create_index("ix_shipments_shipped_on", "shipments", ["shipped_on"])

    categories_table = sa.table(
        "categories",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
        sa.column("gender", sa.String()),
        sa.column("moy_sklad_id", sa.String()),
        sa.column("path_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        categories_table,
        [
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "gender": gender,
                "moy_sklad_id": ms_id,
                "path_name": path_name or None,
                "is_active": True,
                "sort_order": (index + 1) * 10,
            }
            for index, (ms_id, name, gender, path_name) in enumerate(SEED_CATEGORIES)
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_shipments_shipped_on", table_name="shipments")
    op.drop_index("ix_shipments_brand_id", table_name="shipments")
    op.drop_index("ix_shipments_season_id", table_name="shipments")
    op.drop_index("ix_shipments_order_id", table_name="shipments")
    op.drop_table("shipments")

    op.drop_index("ix_payments_kind", table_name="payments")
    op.drop_index("ix_payments_paid_on", table_name="payments")
    op.drop_index("ix_payments_brand_id", table_name="payments")
    op.drop_index("ix_payments_season_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index(
        "ix_brand_order_category_lines_category_id",
        table_name="brand_order_category_lines",
    )
    op.drop_index(
        "ix_brand_order_category_lines_order_id",
        table_name="brand_order_category_lines",
    )
    op.drop_table("brand_order_category_lines")

    op.drop_index("ix_brand_orders_brand_id", table_name="brand_orders")
    op.drop_index("ix_brand_orders_season_id", table_name="brand_orders")
    op.drop_table("brand_orders")

    op.drop_index("ix_fx_rates_valid_to", table_name="fx_rates")
    op.drop_index("ix_fx_rates_valid_from", table_name="fx_rates")
    op.drop_table("fx_rates")

    op.drop_index("ix_categories_moy_sklad_id", table_name="categories")
    op.drop_index("ix_categories_gender", table_name="categories")
    op.drop_index("ix_categories_name", table_name="categories")
    op.drop_table("categories")

    op.drop_index("ix_seasons_code", table_name="seasons")
    op.drop_index("ix_seasons_name", table_name="seasons")
    op.drop_table("seasons")

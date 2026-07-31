"""Схемы админки закупок: сезоны, категории, заказы, оплаты, поставки, курсы."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderGender = Literal["men", "women", "mixed"]
CategoryGender = Literal["men", "women", "unisex"]
PaymentKind = Literal["prepayment", "main"]

_ORM = {"from_attributes": True}


# --- Сезоны ---------------------------------------------------------------


class SeasonOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    is_primary: bool = False
    sort_order: int
    created_at: datetime

    model_config = _ORM


class SeasonListResponse(BaseModel):
    items: list[SeasonOut]


class SeasonCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=32)
    is_active: bool = True
    is_primary: bool = False
    sort_order: int = 0


class SeasonUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None
    is_primary: bool | None = None
    sort_order: int | None = None


# --- Категории ------------------------------------------------------------


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    gender: str
    moy_sklad_id: str | None = None
    path_name: str | None = None
    is_active: bool
    sort_order: int

    model_config = _ORM


class CategoryListResponse(BaseModel):
    items: list[CategoryOut]


class CategoryUpdateRequest(BaseModel):
    """Правим только то, что относится к закупкам; имя и id приходят из МойСклад."""

    is_active: bool | None = None
    sort_order: int | None = None


# --- Курсы ----------------------------------------------------------------


class FxRateOut(BaseModel):
    id: uuid.UUID
    valid_from: date
    valid_to: date | None = None
    eur_rub: Decimal
    comment: str | None = None
    created_at: datetime

    model_config = _ORM


class FxRateListResponse(BaseModel):
    items: list[FxRateOut]


class FxRateCreateRequest(BaseModel):
    valid_from: date
    # Пусто / null = действует бессрочно с valid_from.
    valid_to: date | None = None
    eur_rub: Decimal = Field(gt=0)
    comment: str | None = None


class FxRateUpdateRequest(BaseModel):
    valid_from: date | None = None
    valid_to: date | None = None
    clear_valid_to: bool = False
    eur_rub: Decimal | None = Field(default=None, gt=0)
    comment: str | None = None


# --- Заказы ---------------------------------------------------------------


class OrderLineIn(BaseModel):
    category_id: uuid.UUID
    amount_eur: Decimal = Field(ge=0)
    comment: str | None = None


class OrderLineOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    category_gender: str
    amount_eur: Decimal
    comment: str | None = None


class OrderOut(BaseModel):
    id: uuid.UUID
    season_id: uuid.UUID
    season_name: str
    brand_id: uuid.UUID
    brand_name: str
    gender: str | None = None
    ordered_on: date | None = None
    amount_eur: Decimal
    eur_rub_rate: Decimal | None = None
    amount_rub: Decimal | None = None
    has_prepayment: bool
    prepayment_amount_eur: Decimal | None = None
    prepayment_due_on: date | None = None
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineOut] = Field(default_factory=list)
    # Факт по заказу
    paid_eur: Decimal = Decimal("0")
    prepaid_eur: Decimal = Decimal("0")
    shipped_eur: Decimal = Decimal("0")
    balance_to_pay_eur: Decimal = Decimal("0")
    balance_to_ship_eur: Decimal = Decimal("0")
    prepayment_outstanding_eur: Decimal = Decimal("0")


class OrderListResponse(BaseModel):
    items: list[OrderOut]
    total: int


class OrderCreateRequest(BaseModel):
    season_id: uuid.UUID
    brand_id: uuid.UUID
    gender: OrderGender | None = None
    ordered_on: date | None = None
    # Игнорируется, если переданы строки: сумма считается как их сумма.
    amount_eur: Decimal | None = Field(default=None, ge=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    has_prepayment: bool = False
    prepayment_amount_eur: Decimal | None = Field(default=None, ge=0)
    prepayment_due_on: date | None = None
    comment: str | None = None
    lines: list[OrderLineIn] = Field(default_factory=list)


class OrderUpdateRequest(BaseModel):
    season_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    gender: OrderGender | None = None
    ordered_on: date | None = None
    amount_eur: Decimal | None = Field(default=None, ge=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    has_prepayment: bool | None = None
    prepayment_amount_eur: Decimal | None = Field(default=None, ge=0)
    prepayment_due_on: date | None = None
    comment: str | None = None
    # Если передано — строки заказа заменяются целиком.
    lines: list[OrderLineIn] | None = None


# --- Оплаты ---------------------------------------------------------------


class PaymentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID
    season_name: str
    brand_id: uuid.UUID
    brand_name: str
    paid_on: date
    kind: str
    amount_eur: Decimal
    eur_rub_rate: Decimal | None = None
    amount_rub: Decimal | None = None
    comment: str | None = None
    created_at: datetime


class PaymentListResponse(BaseModel):
    items: list[PaymentOut]
    total: int


class PaymentCreateRequest(BaseModel):
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID
    brand_id: uuid.UUID
    paid_on: date
    kind: PaymentKind = "main"
    amount_eur: Decimal = Field(gt=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    comment: str | None = None


class PaymentUpdateRequest(BaseModel):
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    paid_on: date | None = None
    kind: PaymentKind | None = None
    amount_eur: Decimal | None = Field(default=None, gt=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    comment: str | None = None
    clear_order: bool = False


# --- Поставки -------------------------------------------------------------


class ShipmentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID
    season_name: str
    brand_id: uuid.UUID
    brand_name: str
    shipped_on: date
    amount_eur: Decimal
    weight_kg: Decimal | None = None
    eur_rub_rate: Decimal | None = None
    amount_rub: Decimal | None = None
    comment: str | None = None
    created_at: datetime


class ShipmentListResponse(BaseModel):
    items: list[ShipmentOut]
    total: int


class ShipmentCreateRequest(BaseModel):
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID
    brand_id: uuid.UUID
    shipped_on: date
    amount_eur: Decimal = Field(gt=0)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    comment: str | None = None


class ShipmentUpdateRequest(BaseModel):
    order_id: uuid.UUID | None = None
    season_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    shipped_on: date | None = None
    amount_eur: Decimal | None = Field(default=None, gt=0)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    eur_rub_rate: Decimal | None = Field(default=None, gt=0)
    comment: str | None = None
    clear_order: bool = False


# --- Статистика по бренду -------------------------------------------------


class BrandSeasonStatOut(BaseModel):
    season_id: uuid.UUID
    season_name: str
    orders_count: int
    orders_eur: Decimal
    paid_eur: Decimal
    shipped_eur: Decimal
    balance_to_pay_eur: Decimal
    balance_to_ship_eur: Decimal


class BrandCategoryStatOut(BaseModel):
    category_id: uuid.UUID
    category_name: str
    category_gender: str
    amount_eur: Decimal


class BrandStatsOut(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    orders_count: int
    orders_eur: Decimal
    paid_eur: Decimal
    prepaid_eur: Decimal
    main_paid_eur: Decimal
    shipped_eur: Decimal
    shipped_weight_kg: Decimal
    balance_to_pay_eur: Decimal
    balance_to_ship_eur: Decimal
    prepayment_due_eur: Decimal
    nearest_prepayment_due_on: date | None = None
    by_season: list[BrandSeasonStatOut] = Field(default_factory=list)
    by_category: list[BrandCategoryStatOut] = Field(default_factory=list)


class BrandStatsListResponse(BaseModel):
    items: list[BrandStatsOut]


# --- Дашборд сезона -------------------------------------------------------


class SeasonDashboardTotalsOut(BaseModel):
    orders_count: int
    orders_eur: Decimal
    paid_eur: Decimal
    shipped_eur: Decimal
    balance_to_pay_eur: Decimal
    balance_to_ship_eur: Decimal


class SeasonGenderStatOut(BaseModel):
    gender: str  # men | women | mixed | unknown
    orders_count: int
    orders_eur: Decimal


class SeasonCategoryStatOut(BaseModel):
    category_id: uuid.UUID
    category_name: str
    category_gender: str
    amount_eur: Decimal
    share: float = 0  # 0..1 от суммы категорий этого пола


class SeasonBrandStatOut(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    orders_count: int
    amount_eur: Decimal
    share: float = 0  # 0..1 от суммы заказов сезона


class SeasonDashboardOut(BaseModel):
    season_id: uuid.UUID
    season_name: str
    season_code: str
    is_primary: bool
    totals: SeasonDashboardTotalsOut
    by_gender: list[SeasonGenderStatOut] = Field(default_factory=list)
    by_brand: list[SeasonBrandStatOut] = Field(default_factory=list)
    by_category_men: list[SeasonCategoryStatOut] = Field(default_factory=list)
    by_category_women: list[SeasonCategoryStatOut] = Field(default_factory=list)


# --- Справочники для форм -------------------------------------------------


class BrandRefOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = _ORM


class ProcurementRefsOut(BaseModel):
    seasons: list[SeasonOut]
    categories: list[CategoryOut]
    brands: list[BrandRefOut]
    latest_fx_rate: FxRateOut | None = None


# --- Подсказки для заказа (остатки / размеры) ------------------------------


class OrderGuidancePeriodOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    from_: str = Field(alias="from")
    to: str


class OrderGuidanceStockTotalsOut(BaseModel):
    total: int
    fresh_vl26: int
    old: int


class OrderGuidanceSizeSalesChartOut(BaseModel):
    period: OrderGuidancePeriodOut
    axis_x: str
    axis_y: str
    labels: list[str]
    sellQuantity: list[int]
    seasons: list[str] = Field(default_factory=list)


class OrderGuidanceSizeSummaryRowOut(BaseModel):
    size: str
    received_total: int
    sold_total: int
    stock_total: int


class OrderGuidanceCategoryOut(BaseModel):
    key: str
    name: str
    gender: str
    moy_sklad_id: str | None = None
    order_amount_eur: float
    comment: str
    reinforce_sizes: list[str] = Field(default_factory=list)
    weaken_sizes: list[str] = Field(default_factory=list)
    stock_totals: OrderGuidanceStockTotalsOut
    size_summary_rows: list[OrderGuidanceSizeSummaryRowOut] = Field(default_factory=list)
    size_sales_chart: OrderGuidanceSizeSalesChartOut


class OrderGuidanceMetaOut(BaseModel):
    as_of: str | None = None
    sales_period: OrderGuidancePeriodOut | None = None
    scenario: str | None = None
    comment_format: str | None = None
    chart_rule: str | None = None
    stock_rule: str | None = None
    hint_rule: str | None = None
    fresh_definition: str | None = None
    old_definition: str | None = None
    table_rule: str | None = None


class OrderGuidanceOut(BaseModel):
    meta: OrderGuidanceMetaOut
    categories: list[OrderGuidanceCategoryOut]

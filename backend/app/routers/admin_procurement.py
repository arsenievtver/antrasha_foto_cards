"""Админка закупок у иностранных брендов: сезоны, заказы, оплаты, поставки.

Суммы ведём в евро; рубли считаем по курсу документа (у оплат и поставок он
фиксируется на дату документа, чтобы правка справочника курсов не меняла историю).
Доступ: суперпользователь или сотрудник с правом product.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.models import (
    Brand,
    BrandOrder,
    BrandOrderCategoryLine,
    Category,
    FxRate,
    Payment,
    Season,
    Shipment,
)
from app.models.payment import PAYMENT_KIND_PREPAYMENT
from app.schemas.procurement import (
    BrandCategoryStatOut,
    BrandRefOut,
    BrandSeasonStatOut,
    BrandStatsListResponse,
    BrandStatsOut,
    CategoryListResponse,
    CategoryOrderInsightOut,
    CategoryOut,
    CategoryUpdateRequest,
    FxRateCreateRequest,
    FxRateListResponse,
    FxRateOut,
    FxRateUpdateRequest,
    OrderCreateRequest,
    OrderGuidanceCategoryOut,
    OrderGuidanceOut,
    OrderLineIn,
    OrderLineOut,
    OrderListResponse,
    OrderOut,
    OrderUpdateRequest,
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentOut,
    PaymentUpdateRequest,
    PrepaymentItemOut,
    PrepaymentOverviewOut,
    PrepaymentSeasonOut,
    PrepaymentSeasonTotalsOut,
    ProcurementRefsOut,
    SeasonBrandStatOut,
    SeasonCategoryStatOut,
    SeasonCreateRequest,
    SeasonDashboardListResponse,
    SeasonDashboardOut,
    SeasonDashboardTotalsOut,
    SeasonGenderStatOut,
    SeasonListResponse,
    SeasonOut,
    SeasonUpdateRequest,
    ShipmentCreateRequest,
    ShipmentListResponse,
    ShipmentOut,
    ShipmentUpdateRequest,
)

_ORDER_GUIDANCE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "order_guidance_vl2027.json"
)

log = logging.getLogger("app.api.admin_procurement")

router = APIRouter(prefix="/admin", tags=["admin-procurement"])

ZERO = Decimal("0")
_CENTS = Decimal("0.01")

_CATEGORY_ALIAS_TO_CANONICAL_MS_ID = {
    "463e7bec-34dd-11f1-0a80-148d00118078": "79292943-9e44-11e9-9ff4-31500007d6f3",
    "8ade28c6-6e3e-11f1-0a80-00b0001171b1": "78fabba1-9e44-11e9-9ff4-31500007d6c1",
}

_CANONICAL_CATEGORY_DISPLAY = {
    "0ebca617-f97a-11e9-0a80-0579004f6022": ("Верхняя одежда муж", "men"),
    "009bd151-b37b-11e9-9ff4-3150003a1bb1": ("Пиджаки, жакеты, бомбер муж", "men"),
    "46a5c5b7-5708-11e9-9ff4-315000d0798d": ("Футболки, поло муж", "men"),
    "46b4f0d3-5708-11e9-9ff4-315000d079ad": ("Брюки, джинсы муж", "men"),
    "55edd126-8bff-11f1-0a80-142f000aee50": ("Бриджи, шорты муж", "men"),
    "7958c78e-9e44-11e9-9ff4-31500007d713": ("Трикотаж муж", "men"),
    "797d0e35-9e44-11e9-9ff4-31500007d733": ("Рубашки", "men"),
    "eec41100-9847-11eb-0a80-0616000ac009": ("Костюмы муж", "men"),
    "f8fae156-b37a-11e9-9ff4-3150003a11ec": ("Обувь муж", "men"),
    "0dea4445-f97a-11e9-0a80-0579004f5ecf": ("Верхняя одежда жен", "women"),
    "79292943-9e44-11e9-9ff4-31500007d6f3": ("Пиджаки, жакеты, бомбер жен", "women"),
    "f7b6946e-b37a-11e9-9ff4-3150003a0ff5": ("Футболки, поло, топы жен", "women"),
    "21e1d207-b53f-11e9-9ff4-31500015315b": ("Блузки, рубашки жен", "women"),
    "cd27a401-d3a6-11e9-0a80-02690003e199": ("Трикотаж жен", "women"),
    "78fabba1-9e44-11e9-9ff4-31500007d6c1": ("Брюки, джинсы жен", "women"),
    "4643b20e-8bfa-11f1-0a80-18830009f9ac": ("Бриджи, шорты жен", "women"),
    "65dca14b-8bfd-11f1-0a80-0fbf000a6721": ("Платья жен", "women"),
    "26114fa1-a495-11e9-9ff4-3150000fa9a1": ("Юбки жен", "women"),
    "79419e87-9e44-11e9-9ff4-31500007d6fe": ("Обувь жен", "women"),
    "82adf299-8e8b-11e9-9ff4-31500007fc47": ("Аксессуары муж", "men"),
}

_ACCESSORIES_MS_ID = "82adf299-8e8b-11e9-9ff4-31500007fc47"


def _money(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _canonical_ms_id(ms_id: str | None) -> str | None:
    if not ms_id:
        return ms_id
    return _CATEGORY_ALIAS_TO_CANONICAL_MS_ID.get(ms_id, ms_id)


def _guidance_folder_ms_id(category: Category) -> str | None:
    """Папка МС для подсказок по остаткам. Женские аксессуары делят корневую папку с мужскими."""
    ms_id = _canonical_ms_id(category.moy_sklad_id)
    if ms_id:
        return ms_id
    name = (category.name or "").casefold()
    if name.startswith("аксессуар"):
        return _ACCESSORIES_MS_ID
    return None


def _guidance_category_for(
    payload: dict, folder_ms_id: str | None, gender: str | None
) -> dict | None:
    if not folder_ms_id:
        return None
    fallback: dict | None = None
    for cat in payload.get("categories") or []:
        if _canonical_ms_id(cat.get("moy_sklad_id")) != folder_ms_id:
            continue
        cat_gender = cat.get("gender")
        if cat_gender == gender:
            return cat
        if cat_gender in (None, "unisex") and fallback is None:
            fallback = cat
    return fallback


def _category_out(category: Category) -> CategoryOut:
    ms_id = _canonical_ms_id(category.moy_sklad_id)
    display_name, display_gender = _CANONICAL_CATEGORY_DISPLAY.get(
        ms_id, (category.name, category.gender)
    )
    return CategoryOut(
        id=category.id,
        name=display_name,
        gender=display_gender,
        moy_sklad_id=ms_id,
        path_name=category.path_name,
        is_active=category.is_active,
        sort_order=category.sort_order,
    )


def _normalize_categories(rows: list[Category]) -> list[CategoryOut]:
    normalized: dict[str, Category] = {}
    passthrough: list[CategoryOut] = []
    for row in rows:
        ms_id = _canonical_ms_id(row.moy_sklad_id)
        if not ms_id:
            passthrough.append(_category_out(row))
            continue
        current = normalized.get(ms_id)
        if current is None or (not current.is_active and row.is_active):
            normalized[ms_id] = row

    ordered = sorted(normalized.values(), key=lambda r: (r.sort_order, r.name))
    result = [_category_out(row) for row in ordered] + passthrough
    return sorted(result, key=lambda c: (c.sort_order, c.name))


def _to_rub(amount_eur: Decimal | None, rate: Decimal | None) -> Decimal | None:
    if amount_eur is None or rate is None:
        return None
    return _money(Decimal(amount_eur) * Decimal(rate))


def _resolve_rate(
    db: Session, explicit: Decimal | None, on_date: date
) -> Decimal | None:
    """Курс документа: явный, иначе из справочника на период, покрывающий дату."""
    if explicit is not None:
        return explicit
    row = db.scalars(
        select(FxRate)
        .where(
            FxRate.valid_from <= on_date,
            (FxRate.valid_to.is_(None)) | (FxRate.valid_to >= on_date),
        )
        .order_by(FxRate.valid_from.desc())
        .limit(1)
    ).first()
    return row.eur_rub if row else None


def _assert_period(valid_from: date, valid_to: date | None) -> None:
    if valid_to is not None and valid_to < valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Конец периода раньше начала",
        )


def _periods_overlap(
    a_from: date,
    a_to: date | None,
    b_from: date,
    b_to: date | None,
) -> bool:
    """Пересечение закрытых интервалов; None в конце = +∞."""
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from <= b_end and b_from <= a_end


def _assert_no_overlap(
    db: Session,
    valid_from: date,
    valid_to: date | None,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    rows = db.scalars(select(FxRate)).all()
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        if _periods_overlap(valid_from, valid_to, row.valid_from, row.valid_to):
            other_to = row.valid_to.isoformat() if row.valid_to else "∞"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Период пересекается с уже заданным курсом "
                    f"{row.valid_from.isoformat()}–{other_to} ({row.eur_rub})"
                ),
            )


def _get_season(db: Session, season_id: uuid.UUID) -> Season:
    row = db.get(Season, season_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сезон не найден"
        )
    return row


def _get_brand(db: Session, brand_id: uuid.UUID) -> Brand:
    row = db.get(Brand, brand_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Бренд не найден"
        )
    return row


def _get_order(db: Session, order_id: uuid.UUID) -> BrandOrder:
    row = db.get(BrandOrder, order_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    return row


def _assert_order_matches(order: BrandOrder, season_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    if order.season_id != season_id or order.brand_id != brand_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сезон и бренд документа должны совпадать с заказом",
        )


# --- Сезоны ---------------------------------------------------------------


def _clear_other_order_plan_seasons(db: Session, keep_id: uuid.UUID | None = None) -> None:
    stmt = update(Season).where(Season.is_order_plan.is_(True)).values(is_order_plan=False)
    if keep_id is not None:
        stmt = stmt.where(Season.id != keep_id)
    db.execute(stmt)


def _order_plan_season(db: Session) -> Season | None:
    return db.scalars(
        select(Season).where(Season.is_order_plan.is_(True)).limit(1)
    ).first()


def _list_dashboard_seasons(
    db: Session, season_id: uuid.UUID | None
) -> list[Season]:
    """Сезоны для PWA-дашборда: один по id или все с is_primary по sort_order."""
    if season_id is not None:
        return [_get_season(db, season_id)]
    rows = list(
        db.scalars(
            select(Season)
            .where(Season.is_primary.is_(True))
            .order_by(Season.sort_order.desc(), Season.created_at.desc())
        ).all()
    )
    if rows:
        return rows
    # Совместимость: если никто не отмечен — один активный с наибольшим sort_order.
    fallback = db.scalars(
        select(Season)
        .where(Season.is_active.is_(True))
        .order_by(Season.sort_order.desc(), Season.created_at.desc())
        .limit(1)
    ).first()
    if fallback:
        return [fallback]
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Нет сезонов для дашборда — создайте сезон и отметьте его в колонке PWA",
    )


@router.get("/seasons", response_model=SeasonListResponse)
def list_seasons(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> SeasonListResponse:
    _ = _su
    rows = db.scalars(
        select(Season).order_by(Season.sort_order.desc(), Season.created_at.desc())
    ).all()
    return SeasonListResponse(items=[SeasonOut.model_validate(r) for r in rows])


@router.post("/seasons", response_model=SeasonOut, status_code=status.HTTP_201_CREATED)
def create_season(
    body: SeasonCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> SeasonOut:
    _ = _su
    if body.is_order_plan:
        _clear_other_order_plan_seasons(db)
    row = Season(
        name=body.name.strip(),
        code=body.code.strip(),
        is_active=body.is_active,
        is_primary=body.is_primary,
        is_order_plan=body.is_order_plan,
        sort_order=body.sort_order,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сезон с таким названием или кодом уже есть",
        ) from e
    db.refresh(row)
    return SeasonOut.model_validate(row)


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
def update_season(
    season_id: uuid.UUID,
    body: SeasonUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> SeasonOut:
    _ = _su
    row = _get_season(db, season_id)
    if body.name is not None:
        row.name = body.name.strip()
    if body.code is not None:
        row.code = body.code.strip()
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    if body.is_primary is not None:
        row.is_primary = body.is_primary
    if body.is_order_plan is not None:
        if body.is_order_plan:
            _clear_other_order_plan_seasons(db, keep_id=season_id)
            row.is_order_plan = True
        else:
            row.is_order_plan = False
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сезон с таким названием или кодом уже есть",
        ) from e
    db.refresh(row)
    return SeasonOut.model_validate(row)


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(
    season_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> None:
    _ = _su
    row = _get_season(db, season_id)
    used = db.scalar(
        select(func.count())
        .select_from(BrandOrder)
        .where(BrandOrder.season_id == season_id)
    ) or 0
    used += db.scalar(
        select(func.count()).select_from(Payment).where(Payment.season_id == season_id)
    ) or 0
    used += db.scalar(
        select(func.count()).select_from(Shipment).where(Shipment.season_id == season_id)
    ) or 0
    if used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сезон используется в заказах, оплатах или поставках",
        )
    db.delete(row)
    db.commit()


# --- Категории ------------------------------------------------------------


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(
    gender: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> CategoryListResponse:
    _ = _su
    stmt = select(Category)
    if gender:
        stmt = stmt.where(Category.gender == gender)
    if active_only:
        stmt = stmt.where(Category.is_active.is_(True))
    rows = db.scalars(stmt.order_by(Category.sort_order, Category.name)).all()
    return CategoryListResponse(items=_normalize_categories(rows))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> CategoryOut:
    _ = _su
    row = db.get(Category, category_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена"
        )
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    db.commit()
    db.refresh(row)
    return CategoryOut.model_validate(row)


# --- Курсы ----------------------------------------------------------------


@router.get("/fx-rates", response_model=FxRateListResponse)
def list_fx_rates(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> FxRateListResponse:
    _ = _su
    rows = db.scalars(
        select(FxRate).order_by(FxRate.valid_from.desc()).limit(limit)
    ).all()
    return FxRateListResponse(items=[FxRateOut.model_validate(r) for r in rows])


@router.post("/fx-rates", response_model=FxRateOut, status_code=status.HTTP_201_CREATED)
def create_fx_rate(
    body: FxRateCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> FxRateOut:
    """Новый курс на период. Пересечения с уже заданными периодами запрещены."""
    _ = _su
    _assert_period(body.valid_from, body.valid_to)
    _assert_no_overlap(db, body.valid_from, body.valid_to)
    row = FxRate(
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        eur_rub=body.eur_rub,
        comment=body.comment.strip() if body.comment else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FxRateOut.model_validate(row)


@router.patch("/fx-rates/{rate_id}", response_model=FxRateOut)
def update_fx_rate(
    rate_id: uuid.UUID,
    body: FxRateUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> FxRateOut:
    _ = _su
    row = db.get(FxRate, rate_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    valid_from = body.valid_from if body.valid_from is not None else row.valid_from
    if body.clear_valid_to:
        valid_to = None
    elif body.valid_to is not None:
        valid_to = body.valid_to
    else:
        valid_to = row.valid_to

    _assert_period(valid_from, valid_to)
    _assert_no_overlap(db, valid_from, valid_to, exclude_id=row.id)

    row.valid_from = valid_from
    row.valid_to = valid_to
    if body.eur_rub is not None:
        row.eur_rub = body.eur_rub
    if body.comment is not None:
        row.comment = body.comment.strip() if body.comment else None
    db.commit()
    db.refresh(row)
    return FxRateOut.model_validate(row)


@router.delete("/fx-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fx_rate(
    rate_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> None:
    _ = _su
    row = db.get(FxRate, rate_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    db.delete(row)
    db.commit()


# --- Заказы ---------------------------------------------------------------


def _load_categories(db: Session, lines: list[OrderLineIn]) -> dict[uuid.UUID, Category]:
    if not lines:
        return {}
    ids = {ln.category_id for ln in lines}
    rows = db.scalars(select(Category).where(Category.id.in_(ids))).all()
    found = {r.id: r for r in rows}
    missing = ids - set(found)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Категории не найдены: {', '.join(str(m) for m in sorted(missing, key=str))}",
        )
    canonical_ms_ids = {_canonical_ms_id(row.moy_sklad_id) for row in rows if row.moy_sklad_id}
    canonical_rows = db.scalars(
        select(Category).where(Category.moy_sklad_id.in_(canonical_ms_ids))
    ).all()
    canonical_by_ms_id = {row.moy_sklad_id: row for row in canonical_rows if row.moy_sklad_id}

    normalized: dict[uuid.UUID, Category] = {}
    for input_id, row in found.items():
        canonical_ms_id = _canonical_ms_id(row.moy_sklad_id)
        canonical = canonical_by_ms_id.get(canonical_ms_id or "")
        normalized[input_id] = canonical or row
    return normalized


def _order_facts(
    db: Session, order_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal]]:
    """Суммы оплат, предоплат и поставок по заказам."""
    if not order_ids:
        return {}, {}, {}
    paid = {
        oid: Decimal(total or 0)
        for oid, total in db.execute(
            select(Payment.order_id, func.sum(Payment.amount_eur))
            .where(Payment.order_id.in_(order_ids))
            .group_by(Payment.order_id)
        ).all()
    }
    prepaid = {
        oid: Decimal(total or 0)
        for oid, total in db.execute(
            select(Payment.order_id, func.sum(Payment.amount_eur))
            .where(
                Payment.order_id.in_(order_ids),
                Payment.kind == PAYMENT_KIND_PREPAYMENT,
            )
            .group_by(Payment.order_id)
        ).all()
    }
    shipped = {
        oid: Decimal(total or 0)
        for oid, total in db.execute(
            select(Shipment.order_id, func.sum(Shipment.amount_eur))
            .where(Shipment.order_id.in_(order_ids))
            .group_by(Shipment.order_id)
        ).all()
    }
    return paid, prepaid, shipped


def _order_out(
    order: BrandOrder,
    paid: Decimal,
    prepaid: Decimal,
    shipped: Decimal,
) -> OrderOut:
    amount = _money(order.amount_eur)
    prepayment = _money(order.prepayment_amount_eur) if order.has_prepayment else ZERO
    outstanding = prepayment - _money(prepaid)
    return OrderOut(
        id=order.id,
        season_id=order.season_id,
        season_name=order.season.name if order.season else "",
        brand_id=order.brand_id,
        brand_name=order.brand.name if order.brand else "",
        gender=order.gender,
        ordered_on=order.ordered_on,
        amount_eur=amount,
        eur_rub_rate=order.eur_rub_rate,
        amount_rub=_to_rub(amount, order.eur_rub_rate),
        has_prepayment=order.has_prepayment,
        prepayment_amount_eur=order.prepayment_amount_eur,
        prepayment_due_on=order.prepayment_due_on,
        comment=order.comment,
        created_at=order.created_at,
        updated_at=order.updated_at,
        lines=[
            (
                lambda category_out: OrderLineOut(
                    id=ln.id,
                    category_id=ln.category.id,
                    category_name=category_out.name,
                    category_gender=category_out.gender,
                    amount_eur=_money(ln.amount_eur),
                    comment=ln.comment,
                )
            )(_category_out(ln.category))
            for ln in sorted(
                order.lines,
                key=lambda x: (x.category.sort_order if x.category else 0),
            )
            if ln.category
        ],
        paid_eur=_money(paid),
        prepaid_eur=_money(prepaid),
        shipped_eur=_money(shipped),
        balance_to_pay_eur=amount - _money(paid),
        balance_to_ship_eur=amount - _money(shipped),
        prepayment_outstanding_eur=outstanding if outstanding > ZERO else ZERO,
    )


@router.get("/brand-orders", response_model=OrderListResponse)
def list_brand_orders(
    season_id: uuid.UUID | None = Query(default=None),
    brand_id: uuid.UUID | None = Query(default=None),
    gender: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> OrderListResponse:
    _ = _su
    filters = []
    if season_id:
        filters.append(BrandOrder.season_id == season_id)
    if brand_id:
        filters.append(BrandOrder.brand_id == brand_id)
    if gender:
        filters.append(BrandOrder.gender == gender)

    count_q = select(func.count()).select_from(BrandOrder)
    if filters:
        count_q = count_q.where(*filters)
    total = db.scalar(count_q) or 0

    stmt = select(BrandOrder)
    if filters:
        stmt = stmt.where(*filters)
    rows = db.scalars(
        stmt.options(
            selectinload(BrandOrder.season),
            selectinload(BrandOrder.brand),
            selectinload(BrandOrder.lines).selectinload(BrandOrderCategoryLine.category),
        )
        .order_by(BrandOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    paid, prepaid, shipped = _order_facts(db, [r.id for r in rows])
    return OrderListResponse(
        items=[
            _order_out(
                r,
                paid.get(r.id, ZERO),
                prepaid.get(r.id, ZERO),
                shipped.get(r.id, ZERO),
            )
            for r in rows
        ],
        total=total,
    )


@router.get("/brand-orders/{order_id}", response_model=OrderOut)
def get_brand_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> OrderOut:
    _ = _su
    row = db.scalars(
        select(BrandOrder)
        .where(BrandOrder.id == order_id)
        .options(
            selectinload(BrandOrder.season),
            selectinload(BrandOrder.brand),
            selectinload(BrandOrder.lines).selectinload(BrandOrderCategoryLine.category),
        )
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    paid, prepaid, shipped = _order_facts(db, [row.id])
    return _order_out(
        row, paid.get(row.id, ZERO), prepaid.get(row.id, ZERO), shipped.get(row.id, ZERO)
    )


def _validate_prepayment(
    has_prepayment: bool,
    prepayment_amount: Decimal | None,
    amount_eur: Decimal,
) -> None:
    if not has_prepayment:
        return
    if prepayment_amount is None or prepayment_amount <= ZERO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите сумму предоплаты",
        )
    if amount_eur > ZERO and prepayment_amount > amount_eur:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Предоплата больше суммы заказа",
        )


@router.post("/brand-orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_brand_order(
    body: OrderCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> OrderOut:
    _ = _su
    _get_season(db, body.season_id)
    _get_brand(db, body.brand_id)
    categories = _load_categories(db, body.lines)

    if body.lines:
        amount = _money(sum((ln.amount_eur for ln in body.lines), ZERO))
    else:
        amount = _money(body.amount_eur)
        if amount <= ZERO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите сумму заказа или хотя бы одну категорию",
            )
    _validate_prepayment(body.has_prepayment, body.prepayment_amount_eur, amount)

    order = BrandOrder(
        season_id=body.season_id,
        brand_id=body.brand_id,
        gender=body.gender,
        ordered_on=body.ordered_on,
        amount_eur=amount,
        eur_rub_rate=_resolve_rate(db, body.eur_rub_rate, body.ordered_on or date.today()),
        has_prepayment=body.has_prepayment,
        prepayment_amount_eur=body.prepayment_amount_eur if body.has_prepayment else None,
        prepayment_due_on=body.prepayment_due_on if body.has_prepayment else None,
        comment=body.comment.strip() if body.comment else None,
    )
    for ln in body.lines:
        order.lines.append(
            BrandOrderCategoryLine(
                category_id=categories[ln.category_id].id,
                amount_eur=_money(ln.amount_eur),
                comment=ln.comment.strip() if ln.comment else None,
            )
        )
    db.add(order)
    db.commit()
    log.info("brand order %s created", order.id)
    return get_brand_order(order.id, db=db, _su=_su)


@router.patch("/brand-orders/{order_id}", response_model=OrderOut)
def update_brand_order(
    order_id: uuid.UUID,
    body: OrderUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> OrderOut:
    _ = _su
    order = _get_order(db, order_id)

    if body.season_id is not None:
        _get_season(db, body.season_id)
        order.season_id = body.season_id
    if body.brand_id is not None:
        _get_brand(db, body.brand_id)
        order.brand_id = body.brand_id
    if body.gender is not None:
        order.gender = body.gender
    if body.ordered_on is not None:
        order.ordered_on = body.ordered_on
    if body.comment is not None:
        order.comment = body.comment.strip() if body.comment else None
    if body.eur_rub_rate is not None:
        order.eur_rub_rate = body.eur_rub_rate

    if body.lines is not None:
        categories = _load_categories(db, body.lines)
        order.lines.clear()
        db.flush()
        for ln in body.lines:
            order.lines.append(
                BrandOrderCategoryLine(
                    category_id=categories[ln.category_id].id,
                    amount_eur=_money(ln.amount_eur),
                    comment=ln.comment.strip() if ln.comment else None,
                )
            )
        if body.lines:
            order.amount_eur = _money(sum((ln.amount_eur for ln in body.lines), ZERO))
        else:
            # Пустые строки — заказ без категорий: сумма только из amount_eur.
            if body.amount_eur is None or _money(body.amount_eur) <= ZERO:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Укажите сумму заказа или хотя бы одну категорию",
                )
            order.amount_eur = _money(body.amount_eur)
    elif body.amount_eur is not None:
        order.amount_eur = _money(body.amount_eur)

    if body.has_prepayment is not None:
        order.has_prepayment = body.has_prepayment
    if body.prepayment_amount_eur is not None:
        order.prepayment_amount_eur = body.prepayment_amount_eur
    if body.prepayment_due_on is not None:
        order.prepayment_due_on = body.prepayment_due_on
    if not order.has_prepayment:
        order.prepayment_amount_eur = None
        order.prepayment_due_on = None

    _validate_prepayment(
        order.has_prepayment, order.prepayment_amount_eur, _money(order.amount_eur)
    )
    db.commit()
    return get_brand_order(order.id, db=db, _su=_su)


@router.delete("/brand-orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> None:
    _ = _su
    order = _get_order(db, order_id)
    db.delete(order)
    db.commit()
    log.info("brand order %s deleted", order_id)


# --- Оплаты ---------------------------------------------------------------


def _payment_out(row: Payment) -> PaymentOut:
    return PaymentOut(
        id=row.id,
        order_id=row.order_id,
        season_id=row.season_id,
        season_name=row.season.name if row.season else "",
        brand_id=row.brand_id,
        brand_name=row.brand.name if row.brand else "",
        paid_on=row.paid_on,
        kind=row.kind,
        amount_eur=_money(row.amount_eur),
        eur_rub_rate=row.eur_rub_rate,
        amount_rub=row.amount_rub,
        comment=row.comment,
        created_at=row.created_at,
    )


def _load_payment(db: Session, payment_id: uuid.UUID) -> Payment:
    row = db.scalars(
        select(Payment)
        .where(Payment.id == payment_id)
        .options(selectinload(Payment.season), selectinload(Payment.brand))
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оплата не найдена"
        )
    return row


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> PaymentOut:
    _ = _su
    return _payment_out(_load_payment(db, payment_id))


@router.get("/payments", response_model=PaymentListResponse)
def list_payments(
    season_id: uuid.UUID | None = Query(default=None),
    brand_id: uuid.UUID | None = Query(default=None),
    order_id: uuid.UUID | None = Query(default=None),
    kind: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> PaymentListResponse:
    _ = _su
    filters = []
    if season_id:
        filters.append(Payment.season_id == season_id)
    if brand_id:
        filters.append(Payment.brand_id == brand_id)
    if order_id:
        filters.append(Payment.order_id == order_id)
    if kind:
        filters.append(Payment.kind == kind)

    count_q = select(func.count()).select_from(Payment)
    if filters:
        count_q = count_q.where(*filters)
    total = db.scalar(count_q) or 0

    stmt = select(Payment)
    if filters:
        stmt = stmt.where(*filters)
    rows = db.scalars(
        stmt.options(selectinload(Payment.season), selectinload(Payment.brand))
        .order_by(Payment.paid_on.desc(), Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return PaymentListResponse(items=[_payment_out(r) for r in rows], total=total)


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    body: PaymentCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> PaymentOut:
    _ = _su
    _get_season(db, body.season_id)
    _get_brand(db, body.brand_id)
    if body.order_id:
        _assert_order_matches(
            _get_order(db, body.order_id), body.season_id, body.brand_id
        )

    rate = _resolve_rate(db, body.eur_rub_rate, body.paid_on)
    row = Payment(
        order_id=body.order_id,
        season_id=body.season_id,
        brand_id=body.brand_id,
        paid_on=body.paid_on,
        kind=body.kind,
        amount_eur=_money(body.amount_eur),
        eur_rub_rate=rate,
        amount_rub=_to_rub(body.amount_eur, rate),
        comment=body.comment.strip() if body.comment else None,
    )
    db.add(row)
    db.commit()
    log.info("payment %s created", row.id)
    return _payment_out(_load_payment(db, row.id))


@router.patch("/payments/{payment_id}", response_model=PaymentOut)
def update_payment(
    payment_id: uuid.UUID,
    body: PaymentUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> PaymentOut:
    _ = _su
    row = db.get(Payment, payment_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оплата не найдена"
        )
    if body.season_id is not None:
        _get_season(db, body.season_id)
        row.season_id = body.season_id
    if body.brand_id is not None:
        _get_brand(db, body.brand_id)
        row.brand_id = body.brand_id
    if body.clear_order:
        row.order_id = None
    elif body.order_id is not None:
        _assert_order_matches(_get_order(db, body.order_id), row.season_id, row.brand_id)
        row.order_id = body.order_id
    if body.paid_on is not None:
        row.paid_on = body.paid_on
    if body.kind is not None:
        row.kind = body.kind
    if body.amount_eur is not None:
        row.amount_eur = _money(body.amount_eur)
    if body.eur_rub_rate is not None:
        row.eur_rub_rate = body.eur_rub_rate
    if body.comment is not None:
        row.comment = body.comment.strip() if body.comment else None

    if row.order_id:
        _assert_order_matches(_get_order(db, row.order_id), row.season_id, row.brand_id)
    row.amount_rub = _to_rub(row.amount_eur, row.eur_rub_rate)

    db.commit()
    return _payment_out(_load_payment(db, payment_id))


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> None:
    _ = _su
    row = db.get(Payment, payment_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оплата не найдена"
        )
    db.delete(row)
    db.commit()


# --- Поставки -------------------------------------------------------------


def _shipment_out(row: Shipment) -> ShipmentOut:
    return ShipmentOut(
        id=row.id,
        order_id=row.order_id,
        season_id=row.season_id,
        season_name=row.season.name if row.season else "",
        brand_id=row.brand_id,
        brand_name=row.brand.name if row.brand else "",
        shipped_on=row.shipped_on,
        amount_eur=_money(row.amount_eur),
        weight_kg=row.weight_kg,
        eur_rub_rate=row.eur_rub_rate,
        amount_rub=row.amount_rub,
        comment=row.comment,
        created_at=row.created_at,
    )


def _load_shipment(db: Session, shipment_id: uuid.UUID) -> Shipment:
    row = db.scalars(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.season), selectinload(Shipment.brand))
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Поставка не найдена"
        )
    return row


@router.get("/shipments/{shipment_id}", response_model=ShipmentOut)
def get_shipment(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> ShipmentOut:
    _ = _su
    return _shipment_out(_load_shipment(db, shipment_id))


@router.get("/shipments", response_model=ShipmentListResponse)
def list_shipments(
    season_id: uuid.UUID | None = Query(default=None),
    brand_id: uuid.UUID | None = Query(default=None),
    order_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> ShipmentListResponse:
    _ = _su
    filters = []
    if season_id:
        filters.append(Shipment.season_id == season_id)
    if brand_id:
        filters.append(Shipment.brand_id == brand_id)
    if order_id:
        filters.append(Shipment.order_id == order_id)

    count_q = select(func.count()).select_from(Shipment)
    if filters:
        count_q = count_q.where(*filters)
    total = db.scalar(count_q) or 0

    stmt = select(Shipment)
    if filters:
        stmt = stmt.where(*filters)
    rows = db.scalars(
        stmt.options(selectinload(Shipment.season), selectinload(Shipment.brand))
        .order_by(Shipment.shipped_on.desc(), Shipment.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return ShipmentListResponse(items=[_shipment_out(r) for r in rows], total=total)


@router.post("/shipments", response_model=ShipmentOut, status_code=status.HTTP_201_CREATED)
def create_shipment(
    body: ShipmentCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> ShipmentOut:
    _ = _su
    _get_season(db, body.season_id)
    _get_brand(db, body.brand_id)
    if body.order_id:
        _assert_order_matches(
            _get_order(db, body.order_id), body.season_id, body.brand_id
        )

    rate = _resolve_rate(db, body.eur_rub_rate, body.shipped_on)
    row = Shipment(
        order_id=body.order_id,
        season_id=body.season_id,
        brand_id=body.brand_id,
        shipped_on=body.shipped_on,
        amount_eur=_money(body.amount_eur),
        weight_kg=body.weight_kg,
        eur_rub_rate=rate,
        amount_rub=_to_rub(body.amount_eur, rate),
        comment=body.comment.strip() if body.comment else None,
    )
    db.add(row)
    db.commit()
    log.info("shipment %s created", row.id)
    return _shipment_out(_load_shipment(db, row.id))


@router.patch("/shipments/{shipment_id}", response_model=ShipmentOut)
def update_shipment(
    shipment_id: uuid.UUID,
    body: ShipmentUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> ShipmentOut:
    _ = _su
    row = db.get(Shipment, shipment_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Поставка не найдена"
        )
    if body.season_id is not None:
        _get_season(db, body.season_id)
        row.season_id = body.season_id
    if body.brand_id is not None:
        _get_brand(db, body.brand_id)
        row.brand_id = body.brand_id
    if body.clear_order:
        row.order_id = None
    elif body.order_id is not None:
        _assert_order_matches(_get_order(db, body.order_id), row.season_id, row.brand_id)
        row.order_id = body.order_id
    if body.shipped_on is not None:
        row.shipped_on = body.shipped_on
    if body.amount_eur is not None:
        row.amount_eur = _money(body.amount_eur)
    if body.weight_kg is not None:
        row.weight_kg = body.weight_kg
    if body.eur_rub_rate is not None:
        row.eur_rub_rate = body.eur_rub_rate
    if body.comment is not None:
        row.comment = body.comment.strip() if body.comment else None

    if row.order_id:
        _assert_order_matches(_get_order(db, row.order_id), row.season_id, row.brand_id)
    row.amount_rub = _to_rub(row.amount_eur, row.eur_rub_rate)

    db.commit()
    return _shipment_out(_load_shipment(db, shipment_id))


@router.delete("/shipments/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shipment(
    shipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> None:
    _ = _su
    row = db.get(Shipment, shipment_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Поставка не найдена"
        )
    db.delete(row)
    db.commit()


# --- Статистика -----------------------------------------------------------


def _sum_by_brand(db: Session, column, model, *conditions) -> dict[uuid.UUID, Decimal]:
    stmt = select(model.brand_id, func.sum(column)).group_by(model.brand_id)
    for cond in conditions:
        stmt = stmt.where(cond)
    return {bid: Decimal(total or 0) for bid, total in db.execute(stmt).all()}


def _brand_stats_for_season(
    db: Session, season_id: uuid.UUID
) -> list[SeasonBrandStatOut]:
    """Разбивка заказов сезона по брендам (несколько заказов одного бренда суммируются)."""
    rows = db.execute(
        select(
            Brand.id,
            Brand.name,
            func.count(BrandOrder.id),
            func.sum(BrandOrder.amount_eur),
        )
        .join(BrandOrder, BrandOrder.brand_id == Brand.id)
        .where(BrandOrder.season_id == season_id)
        .group_by(Brand.id, Brand.name)
        .order_by(func.sum(BrandOrder.amount_eur).desc())
    ).all()
    total_amount = sum((Decimal(total or 0) for _, _, _, total in rows), ZERO)
    items: list[SeasonBrandStatOut] = []
    for brand_id, brand_name, cnt, total in rows:
        amount = _money(total)
        share = float(amount / total_amount) if total_amount > ZERO else 0.0
        items.append(
            SeasonBrandStatOut(
                brand_id=brand_id,
                brand_name=brand_name,
                orders_count=int(cnt or 0),
                amount_eur=amount,
                share=share,
            )
        )
    return items


def _category_stats_for_season(
    db: Session,
    season_id: uuid.UUID,
    gender: str,
    *,
    with_plan: bool = False,
) -> list[SeasonCategoryStatOut]:
    """Разбивка строк заказов сезона по категориям указанного пола (men/women).

    При with_plan подмешивает планы из order-guidance и категории с нулевым фактом.
    """
    category_totals: dict[str, dict[str, object]] = {}
    for cid, name, cat_gender, ms_id, total in db.execute(
        select(
            Category.id,
            Category.name,
            Category.gender,
            Category.moy_sklad_id,
            func.sum(BrandOrderCategoryLine.amount_eur),
        )
        .join(
            BrandOrderCategoryLine,
            BrandOrderCategoryLine.category_id == Category.id,
        )
        .join(BrandOrder, BrandOrder.id == BrandOrderCategoryLine.order_id)
        .where(BrandOrder.season_id == season_id)
        .group_by(Category.id, Category.name, Category.gender, Category.moy_sklad_id)
    ).all():
        folder_ms = _canonical_ms_id(ms_id)
        if not folder_ms and (name or "").casefold().startswith("аксессуар"):
            folder_ms = _ACCESSORIES_MS_ID
        display_name, display_gender = _CANONICAL_CATEGORY_DISPLAY.get(
            folder_ms, (name, cat_gender)
        )
        if folder_ms == _ACCESSORIES_MS_ID:
            display_gender = cat_gender if cat_gender in ("men", "women") else gender
            display_name = "Аксессуары жен" if display_gender == "women" else "Аксессуары муж"
        if display_gender != gender:
            continue
        key = f"{folder_ms or cid}:{display_gender}"
        entry = category_totals.setdefault(
            key,
            {
                "category_id": cid,
                "category_name": display_name,
                "category_gender": display_gender,
                "moy_sklad_id": folder_ms,
                "amount_eur": ZERO,
                "plan_eur": None,
            },
        )
        entry["amount_eur"] = Decimal(entry["amount_eur"]) + Decimal(total or 0)

    if with_plan:
        try:
            payload = _load_order_guidance()
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = None
        if payload:
            cat_rows = db.scalars(select(Category).where(Category.is_active.is_(True))).all()
            id_by_ms_gender: dict[tuple[str, str], uuid.UUID] = {}
            for cat in cat_rows:
                ms = _canonical_ms_id(cat.moy_sklad_id)
                if not ms and (cat.name or "").casefold().startswith("аксессуар"):
                    ms = _ACCESSORIES_MS_ID
                if not ms:
                    continue
                cat_gender = cat.gender if cat.gender in ("men", "women") else None
                if cat_gender:
                    id_by_ms_gender.setdefault((ms, cat_gender), cat.id)

            for gcat in payload.get("categories") or []:
                g_gender = gcat.get("gender")
                if g_gender != gender:
                    continue
                folder_ms = _canonical_ms_id(gcat.get("moy_sklad_id"))
                if not folder_ms:
                    continue
                if folder_ms == _ACCESSORIES_MS_ID:
                    display_name = (
                        "Аксессуары жен" if gender == "women" else "Аксессуары муж"
                    )
                else:
                    display_name, display_gender = _CANONICAL_CATEGORY_DISPLAY.get(
                        folder_ms, (gcat.get("name") or folder_ms, gender)
                    )
                    if display_gender != gender:
                        continue
                key = f"{folder_ms}:{gender}"
                plan = _money(gcat.get("order_amount_eur"))
                entry = category_totals.get(key)
                if entry is None:
                    cat_id = id_by_ms_gender.get((folder_ms, gender))
                    if cat_id is None:
                        continue
                    entry = {
                        "category_id": cat_id,
                        "category_name": display_name,
                        "category_gender": gender,
                        "moy_sklad_id": folder_ms,
                        "amount_eur": ZERO,
                        "plan_eur": plan,
                    }
                    category_totals[key] = entry
                else:
                    entry["plan_eur"] = plan
                    entry["category_name"] = display_name

    total_amount = sum((Decimal(e["amount_eur"]) for e in category_totals.values()), ZERO)
    items: list[SeasonCategoryStatOut] = []
    for entry in category_totals.values():
        amount = _money(entry["amount_eur"])
        plan_raw = entry.get("plan_eur")
        plan = _money(plan_raw) if plan_raw is not None else None
        delta = _money(amount - plan) if plan is not None else None
        share = float(amount / total_amount) if total_amount > ZERO else 0.0
        items.append(
            SeasonCategoryStatOut(
                category_id=entry["category_id"],
                category_name=entry["category_name"],
                category_gender=entry["category_gender"],
                amount_eur=amount,
                share=share,
                plan_eur=plan,
                delta_eur=delta,
            )
        )

    if with_plan:
        items.sort(
            key=lambda x: (
                abs(x.delta_eur) if x.delta_eur is not None else ZERO,
                x.plan_eur or ZERO,
            ),
            reverse=True,
        )
    else:
        items.sort(key=lambda x: x.amount_eur, reverse=True)
    return items


def _build_season_dashboard(db: Session, season: Season) -> SeasonDashboardOut:
    orders_count = int(
        db.scalar(
            select(func.count()).select_from(BrandOrder).where(
                BrandOrder.season_id == season.id
            )
        )
        or 0
    )
    orders_eur = _money(
        db.scalar(
            select(func.sum(BrandOrder.amount_eur)).where(
                BrandOrder.season_id == season.id
            )
        )
    )
    paid_eur = _money(
        db.scalar(
            select(func.sum(Payment.amount_eur)).where(Payment.season_id == season.id)
        )
    )
    shipped_eur = _money(
        db.scalar(
            select(func.sum(Shipment.amount_eur)).where(Shipment.season_id == season.id)
        )
    )

    gender_rows = db.execute(
        select(BrandOrder.gender, func.count(), func.sum(BrandOrder.amount_eur))
        .where(BrandOrder.season_id == season.id)
        .group_by(BrandOrder.gender)
    ).all()
    by_gender: list[SeasonGenderStatOut] = []
    for g, cnt, total in gender_rows:
        by_gender.append(
            SeasonGenderStatOut(
                gender=g or "unknown",
                orders_count=int(cnt or 0),
                orders_eur=_money(total),
            )
        )
    by_gender.sort(
        key=lambda x: {"men": 0, "women": 1, "mixed": 2}.get(x.gender, 3),
    )

    with_plan = bool(season.is_order_plan)
    return SeasonDashboardOut(
        season_id=season.id,
        season_name=season.name,
        season_code=season.code,
        is_primary=bool(season.is_primary),
        is_order_plan=with_plan,
        sort_order=int(season.sort_order or 0),
        totals=SeasonDashboardTotalsOut(
            orders_count=orders_count,
            orders_eur=orders_eur,
            paid_eur=paid_eur,
            shipped_eur=shipped_eur,
            balance_to_pay_eur=orders_eur - paid_eur,
            balance_to_ship_eur=orders_eur - shipped_eur,
        ),
        by_gender=by_gender,
        by_brand=_brand_stats_for_season(db, season.id),
        by_category_men=_category_stats_for_season(
            db, season.id, "men", with_plan=with_plan
        ),
        by_category_women=_category_stats_for_season(
            db, season.id, "women", with_plan=with_plan
        ),
    )


@router.get("/procurement/season-dashboard", response_model=SeasonDashboardListResponse)
def get_season_dashboard(
    season_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> SeasonDashboardListResponse:
    """Сводки сезонов для PWA: отмеченные в PWA, по sort_order (убыв.)."""
    _ = _su
    seasons = _list_dashboard_seasons(db, season_id)
    return SeasonDashboardListResponse(
        items=[_build_season_dashboard(db, season) for season in seasons]
    )


_PREPAYMENT_STATUS_RANK = {
    "overdue": 0,
    "due_soon": 1,
    "open": 2,
    "paid": 3,
}

_DUE_SOON_DAYS_DEFAULT = 14


def _prepayment_status(
    outstanding: Decimal,
    due_on: date | None,
    *,
    as_of: date,
    due_soon_days: int,
) -> tuple[str, int | None]:
    """Статус предоплаты и дней до срока (отрицательно = просрочка)."""
    if outstanding <= ZERO:
        days = (due_on - as_of).days if due_on else None
        return "paid", days
    if due_on is None:
        return "open", None
    days = (due_on - as_of).days
    if days < 0:
        return "overdue", days
    if days <= due_soon_days:
        return "due_soon", days
    return "open", days


def _empty_prepayment_totals() -> PrepaymentSeasonTotalsOut:
    return PrepaymentSeasonTotalsOut(
        planned_eur=ZERO,
        paid_eur=ZERO,
        outstanding_eur=ZERO,
        overdue_eur=ZERO,
        due_soon_eur=ZERO,
        orders_count=0,
        overdue_count=0,
        due_soon_count=0,
        open_count=0,
        paid_count=0,
    )


def _build_prepayment_season(
    db: Session,
    season: Season,
    *,
    as_of: date,
    due_soon_days: int,
) -> PrepaymentSeasonOut:
    orders = list(
        db.scalars(
            select(BrandOrder)
            .where(
                BrandOrder.season_id == season.id,
                BrandOrder.has_prepayment.is_(True),
            )
            .options(selectinload(BrandOrder.brand))
            .order_by(BrandOrder.prepayment_due_on.asc().nulls_last(), BrandOrder.created_at.desc())
        ).all()
    )
    _, prepaid_by_order, _ = _order_facts(db, [o.id for o in orders])

    items: list[PrepaymentItemOut] = []
    totals = _empty_prepayment_totals()

    for order in orders:
        planned = _money(order.prepayment_amount_eur)
        if planned <= ZERO:
            continue
        prepaid = _money(prepaid_by_order.get(order.id, ZERO))
        outstanding = planned - prepaid
        if outstanding < ZERO:
            outstanding = ZERO
        status, days = _prepayment_status(
            outstanding,
            order.prepayment_due_on,
            as_of=as_of,
            due_soon_days=due_soon_days,
        )
        items.append(
            PrepaymentItemOut(
                order_id=order.id,
                brand_id=order.brand_id,
                brand_name=order.brand.name if order.brand else "",
                gender=order.gender,
                ordered_on=order.ordered_on,
                order_amount_eur=_money(order.amount_eur),
                prepayment_amount_eur=planned,
                prepaid_eur=prepaid,
                outstanding_eur=outstanding,
                due_on=order.prepayment_due_on,
                days_until_due=days,
                status=status,
            )
        )
        totals.orders_count += 1
        totals.planned_eur += planned
        totals.paid_eur += prepaid
        totals.outstanding_eur += outstanding
        if status == "overdue":
            totals.overdue_count += 1
            totals.overdue_eur += outstanding
        elif status == "due_soon":
            totals.due_soon_count += 1
            totals.due_soon_eur += outstanding
        elif status == "open":
            totals.open_count += 1
        else:
            totals.paid_count += 1

    items.sort(
        key=lambda it: (
            _PREPAYMENT_STATUS_RANK.get(it.status, 9),
            it.days_until_due if it.days_until_due is not None else 10_000,
            it.brand_name.lower(),
        )
    )
    totals.planned_eur = _money(totals.planned_eur)
    totals.paid_eur = _money(totals.paid_eur)
    totals.outstanding_eur = _money(totals.outstanding_eur)
    totals.overdue_eur = _money(totals.overdue_eur)
    totals.due_soon_eur = _money(totals.due_soon_eur)

    return PrepaymentSeasonOut(
        season_id=season.id,
        season_name=season.name,
        season_code=season.code,
        is_primary=bool(season.is_primary),
        sort_order=int(season.sort_order or 0),
        totals=totals,
        items=items,
    )


def _sum_prepayment_totals(
    seasons: list[PrepaymentSeasonOut],
) -> PrepaymentSeasonTotalsOut:
    totals = _empty_prepayment_totals()
    for season in seasons:
        t = season.totals
        totals.planned_eur += t.planned_eur
        totals.paid_eur += t.paid_eur
        totals.outstanding_eur += t.outstanding_eur
        totals.overdue_eur += t.overdue_eur
        totals.due_soon_eur += t.due_soon_eur
        totals.orders_count += t.orders_count
        totals.overdue_count += t.overdue_count
        totals.due_soon_count += t.due_soon_count
        totals.open_count += t.open_count
        totals.paid_count += t.paid_count
    totals.planned_eur = _money(totals.planned_eur)
    totals.paid_eur = _money(totals.paid_eur)
    totals.outstanding_eur = _money(totals.outstanding_eur)
    totals.overdue_eur = _money(totals.overdue_eur)
    totals.due_soon_eur = _money(totals.due_soon_eur)
    return totals


@router.get("/procurement/prepayments", response_model=PrepaymentOverviewOut)
def get_prepayment_overview(
    season_id: uuid.UUID | None = Query(default=None),
    due_soon_days: int = Query(default=_DUE_SOON_DAYS_DEFAULT, ge=1, le=90),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> PrepaymentOverviewOut:
    """Картина предоплат по сезонам дашборда (PWA): сроки, просрочки, итоги."""
    _ = _su
    as_of = date.today()
    seasons = _list_dashboard_seasons(db, season_id)
    items = [
        _build_prepayment_season(
            db, season, as_of=as_of, due_soon_days=due_soon_days
        )
        for season in seasons
    ]
    return PrepaymentOverviewOut(
        as_of=as_of,
        due_soon_days=due_soon_days,
        totals=_sum_prepayment_totals(items),
        items=items,
    )


@router.get("/procurement/brand-stats", response_model=BrandStatsListResponse)
def list_brand_stats(
    season_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> BrandStatsListResponse:
    """Сводка по всем брендам, у которых есть заказы, оплаты или поставки."""
    _ = _su
    order_filter = [BrandOrder.season_id == season_id] if season_id else []
    payment_filter = [Payment.season_id == season_id] if season_id else []
    shipment_filter = [Shipment.season_id == season_id] if season_id else []

    orders_eur = _sum_by_brand(db, BrandOrder.amount_eur, BrandOrder, *order_filter)
    counts_stmt = select(BrandOrder.brand_id, func.count()).group_by(BrandOrder.brand_id)
    for cond in order_filter:
        counts_stmt = counts_stmt.where(cond)
    orders_count = {bid: int(c or 0) for bid, c in db.execute(counts_stmt).all()}

    paid_eur = _sum_by_brand(db, Payment.amount_eur, Payment, *payment_filter)
    prepaid_eur = _sum_by_brand(
        db,
        Payment.amount_eur,
        Payment,
        Payment.kind == PAYMENT_KIND_PREPAYMENT,
        *payment_filter,
    )
    shipped_eur = _sum_by_brand(db, Shipment.amount_eur, Shipment, *shipment_filter)
    shipped_kg = _sum_by_brand(db, Shipment.weight_kg, Shipment, *shipment_filter)

    brand_ids = set(orders_eur) | set(paid_eur) | set(shipped_eur)
    if not brand_ids:
        return BrandStatsListResponse(items=[])
    brands = db.scalars(select(Brand).where(Brand.id.in_(brand_ids))).all()

    items: list[BrandStatsOut] = []
    for brand in sorted(brands, key=lambda b: b.name.lower()):
        orders_total = _money(orders_eur.get(brand.id, ZERO))
        paid_total = _money(paid_eur.get(brand.id, ZERO))
        prepaid_total = _money(prepaid_eur.get(brand.id, ZERO))
        shipped_total = _money(shipped_eur.get(brand.id, ZERO))
        items.append(
            BrandStatsOut(
                brand_id=brand.id,
                brand_name=brand.name,
                orders_count=orders_count.get(brand.id, 0),
                orders_eur=orders_total,
                paid_eur=paid_total,
                prepaid_eur=prepaid_total,
                main_paid_eur=paid_total - prepaid_total,
                shipped_eur=shipped_total,
                shipped_weight_kg=_money(shipped_kg.get(brand.id, ZERO)),
                balance_to_pay_eur=orders_total - paid_total,
                balance_to_ship_eur=orders_total - shipped_total,
                prepayment_due_eur=ZERO,
            )
        )
    return BrandStatsListResponse(items=items)


@router.get("/brands/{brand_id}/procurement-stats", response_model=BrandStatsOut)
def get_brand_procurement_stats(
    brand_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> BrandStatsOut:
    """Заказы, оплаты и поставки бренда: итоги, разбивка по сезонам и категориям."""
    _ = _su
    brand = _get_brand(db, brand_id)

    orders = db.scalars(
        select(BrandOrder)
        .where(BrandOrder.brand_id == brand_id)
        .options(selectinload(BrandOrder.season))
    ).all()
    orders_total = _money(sum((Decimal(o.amount_eur) for o in orders), ZERO))

    paid_total = _money(
        db.scalar(
            select(func.sum(Payment.amount_eur)).where(Payment.brand_id == brand_id)
        )
    )
    prepaid_total = _money(
        db.scalar(
            select(func.sum(Payment.amount_eur)).where(
                Payment.brand_id == brand_id,
                Payment.kind == PAYMENT_KIND_PREPAYMENT,
            )
        )
    )
    shipped_total = _money(
        db.scalar(
            select(func.sum(Shipment.amount_eur)).where(Shipment.brand_id == brand_id)
        )
    )
    shipped_kg = _money(
        db.scalar(
            select(func.sum(Shipment.weight_kg)).where(Shipment.brand_id == brand_id)
        )
    )

    paid_by_season = {
        sid: Decimal(total or 0)
        for sid, total in db.execute(
            select(Payment.season_id, func.sum(Payment.amount_eur))
            .where(Payment.brand_id == brand_id)
            .group_by(Payment.season_id)
        ).all()
    }
    shipped_by_season = {
        sid: Decimal(total or 0)
        for sid, total in db.execute(
            select(Shipment.season_id, func.sum(Shipment.amount_eur))
            .where(Shipment.brand_id == brand_id)
            .group_by(Shipment.season_id)
        ).all()
    }

    seasons: dict[uuid.UUID, dict] = {}
    for order in orders:
        entry = seasons.setdefault(
            order.season_id,
            {
                "name": order.season.name if order.season else "",
                "count": 0,
                "orders": ZERO,
            },
        )
        entry["count"] += 1
        entry["orders"] += Decimal(order.amount_eur)

    for season_id in set(paid_by_season) | set(shipped_by_season):
        if season_id not in seasons:
            season = db.get(Season, season_id)
            seasons[season_id] = {
                "name": season.name if season else "",
                "count": 0,
                "orders": ZERO,
            }

    by_season = []
    for season_id, entry in seasons.items():
        season_orders = _money(entry["orders"])
        season_paid = _money(paid_by_season.get(season_id, ZERO))
        season_shipped = _money(shipped_by_season.get(season_id, ZERO))
        by_season.append(
            BrandSeasonStatOut(
                season_id=season_id,
                season_name=entry["name"],
                orders_count=entry["count"],
                orders_eur=season_orders,
                paid_eur=season_paid,
                shipped_eur=season_shipped,
                balance_to_pay_eur=season_orders - season_paid,
                balance_to_ship_eur=season_orders - season_shipped,
            )
        )
    by_season.sort(key=lambda s: s.orders_eur, reverse=True)

    category_totals: dict[str, dict[str, object]] = {}
    for cid, name, gender, ms_id, total in db.execute(
        select(
            Category.id,
            Category.name,
            Category.gender,
            Category.moy_sklad_id,
            func.sum(BrandOrderCategoryLine.amount_eur),
        )
        .join(
            BrandOrderCategoryLine,
            BrandOrderCategoryLine.category_id == Category.id,
        )
        .join(BrandOrder, BrandOrder.id == BrandOrderCategoryLine.order_id)
        .where(BrandOrder.brand_id == brand_id)
        .group_by(Category.id, Category.name, Category.gender, Category.moy_sklad_id)
    ).all():
        canonical_ms_id = _canonical_ms_id(ms_id)
        display_name, display_gender = _CANONICAL_CATEGORY_DISPLAY.get(
            canonical_ms_id, (name, gender)
        )
        key = canonical_ms_id or str(cid)
        entry = category_totals.setdefault(
            key,
            {
                "category_id": cid,
                "category_name": display_name,
                "category_gender": display_gender,
                "amount_eur": ZERO,
            },
        )
        entry["amount_eur"] = Decimal(entry["amount_eur"]) + Decimal(total or 0)

    by_category = [
        BrandCategoryStatOut(
            category_id=entry["category_id"],
            category_name=entry["category_name"],
            category_gender=entry["category_gender"],
            amount_eur=_money(entry["amount_eur"]),
        )
        for entry in sorted(
            category_totals.values(),
            key=lambda item: Decimal(item["amount_eur"]),
            reverse=True,
        )
    ]

    prepaid_by_order = {
        oid: Decimal(total or 0)
        for oid, total in db.execute(
            select(Payment.order_id, func.sum(Payment.amount_eur))
            .where(
                Payment.brand_id == brand_id,
                Payment.kind == PAYMENT_KIND_PREPAYMENT,
                Payment.order_id.isnot(None),
            )
            .group_by(Payment.order_id)
        ).all()
    }
    prepayment_due = ZERO
    due_dates: list[date] = []
    for order in orders:
        if not order.has_prepayment or order.prepayment_amount_eur is None:
            continue
        outstanding = Decimal(order.prepayment_amount_eur) - prepaid_by_order.get(
            order.id, ZERO
        )
        if outstanding > ZERO:
            prepayment_due += outstanding
            if order.prepayment_due_on:
                due_dates.append(order.prepayment_due_on)

    return BrandStatsOut(
        brand_id=brand.id,
        brand_name=brand.name,
        orders_count=len(orders),
        orders_eur=orders_total,
        paid_eur=paid_total,
        prepaid_eur=prepaid_total,
        main_paid_eur=paid_total - prepaid_total,
        shipped_eur=shipped_total,
        shipped_weight_kg=shipped_kg,
        balance_to_pay_eur=orders_total - paid_total,
        balance_to_ship_eur=orders_total - shipped_total,
        prepayment_due_eur=_money(prepayment_due),
        nearest_prepayment_due_on=min(due_dates) if due_dates else None,
        by_season=by_season,
        by_category=by_category,
    )


@router.get("/procurement/refs", response_model=ProcurementRefsOut)
def get_procurement_refs(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> ProcurementRefsOut:
    """Справочники для форм: сезоны, категории, бренды и последний курс."""
    _ = _su
    seasons = db.scalars(
        select(Season).order_by(Season.sort_order.desc(), Season.created_at.desc())
    ).all()
    categories = db.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.name)
    ).all()
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    today = date.today()
    current = db.scalars(
        select(FxRate)
        .where(
            FxRate.valid_from <= today,
            (FxRate.valid_to.is_(None)) | (FxRate.valid_to >= today),
        )
        .order_by(FxRate.valid_from.desc())
        .limit(1)
    ).first()
    return ProcurementRefsOut(
        seasons=[SeasonOut.model_validate(s) for s in seasons],
        categories=_normalize_categories(categories),
        brands=[BrandRefOut.model_validate(b) for b in brands],
        latest_fx_rate=FxRateOut.model_validate(current) if current else None,
    )


@lru_cache(maxsize=1)
def _load_order_guidance() -> dict:
    if not _ORDER_GUIDANCE_PATH.is_file():
        raise FileNotFoundError(str(_ORDER_GUIDANCE_PATH))
    payload = json.loads(_ORDER_GUIDANCE_PATH.read_text(encoding="utf-8"))
    meta = payload.get("meta") or {}
    meta.pop("raw_dir", None)
    payload["meta"] = meta
    return payload


@router.get("/procurement/order-guidance", response_model=OrderGuidanceOut)
def get_order_guidance(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> OrderGuidanceOut:
    """Подсказки по размерам для закупки: комментарии и графики продаж."""
    _ = _su
    try:
        payload = _load_order_guidance()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл подсказок для заказа не найден",
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        log.exception("order-guidance load failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось прочитать подсказки для заказа",
        ) from exc
    out = OrderGuidanceOut.model_validate(payload)
    season = _order_plan_season(db)
    if season is not None:
        out.season_id = season.id
        out.season_name = season.name
        out.season_code = season.code
    return out


def _category_ids_for_canonical_ms(
    db: Session, canonical_ms_id: str | None, fallback_id: uuid.UUID
) -> list[uuid.UUID]:
    """Все category.id, которые относятся к той же канонической папке МС (с алиасами)."""
    if not canonical_ms_id:
        return [fallback_id]
    alias_ms_ids = [
        alias
        for alias, target in _CATEGORY_ALIAS_TO_CANONICAL_MS_ID.items()
        if target == canonical_ms_id
    ]
    ms_ids = [canonical_ms_id, *alias_ms_ids]
    rows = db.scalars(
        select(Category.id).where(Category.moy_sklad_id.in_(ms_ids))
    ).all()
    ids = list(rows)
    if fallback_id not in ids:
        ids.append(fallback_id)
    return ids


@router.get(
    "/procurement/category-order-insight",
    response_model=CategoryOrderInsightOut,
)
def get_category_order_insight(
    category_id: uuid.UUID = Query(...),
    season_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("product")),
) -> CategoryOrderInsightOut:
    """Живая сводка по категории для формы заказа: рекомендации + заказы по брендам."""
    _ = _su
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена"
        )
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сезон не найден"
        )

    canonical_ms_id = _canonical_ms_id(category.moy_sklad_id)
    display_name, _ = _CANONICAL_CATEGORY_DISPLAY.get(
        canonical_ms_id, (category.name, category.gender)
    )
    related_ids = _category_ids_for_canonical_ms(db, canonical_ms_id, category.id)
    guidance_ms_id = _guidance_folder_ms_id(category)

    brand_rows = db.execute(
        select(
            Brand.id,
            Brand.name,
            func.sum(BrandOrderCategoryLine.amount_eur),
            func.count(func.distinct(BrandOrder.id)),
        )
        .join(BrandOrder, BrandOrder.brand_id == Brand.id)
        .join(
            BrandOrderCategoryLine,
            BrandOrderCategoryLine.order_id == BrandOrder.id,
        )
        .where(
            BrandOrder.season_id == season_id,
            BrandOrderCategoryLine.category_id.in_(related_ids),
        )
        .group_by(Brand.id, Brand.name)
        .order_by(func.sum(BrandOrderCategoryLine.amount_eur).desc())
    ).all()

    brands = [
        {
            "brand_id": brand_id,
            "brand_name": brand_name,
            "amount_eur": _money(total),
            "orders_count": int(cnt or 0),
        }
        for brand_id, brand_name, total, cnt in brand_rows
    ]
    ordered_eur = _money(sum((row["amount_eur"] for row in brands), ZERO))

    guidance_out: OrderGuidanceCategoryOut | None = None
    budget_eur: Decimal | None = None
    remaining_eur: Decimal | None = None
    try:
        payload = _load_order_guidance()
        cat = _guidance_category_for(payload, guidance_ms_id, category.gender)
        if cat:
            guidance_out = OrderGuidanceCategoryOut.model_validate(cat)
            budget_eur = _money(guidance_out.order_amount_eur)
            remaining_eur = _money(budget_eur - ordered_eur)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        log.exception("category-order-insight guidance load failed")

    return CategoryOrderInsightOut(
        category_id=category.id,
        category_name=display_name,
        moy_sklad_id=guidance_ms_id,
        season_id=season.id,
        budget_eur=budget_eur,
        ordered_eur=ordered_eur,
        remaining_eur=remaining_eur,
        guidance=guidance_out,
        brands=brands,
    )

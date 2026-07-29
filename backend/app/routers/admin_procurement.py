"""Админка закупок у иностранных брендов: сезоны, заказы, оплаты, поставки.

Суммы ведём в евро; рубли считаем по курсу документа (у оплат и поставок он
фиксируется на дату документа, чтобы правка справочника курсов не меняла историю).
Доступ: суперпользователь или сотрудник с правом product.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
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
    CategoryOut,
    CategoryUpdateRequest,
    FxRateCreateRequest,
    FxRateListResponse,
    FxRateOut,
    FxRateUpdateRequest,
    OrderCreateRequest,
    OrderLineIn,
    OrderLineOut,
    OrderListResponse,
    OrderOut,
    OrderUpdateRequest,
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentOut,
    PaymentUpdateRequest,
    ProcurementRefsOut,
    SeasonCreateRequest,
    SeasonListResponse,
    SeasonOut,
    SeasonUpdateRequest,
    ShipmentCreateRequest,
    ShipmentListResponse,
    ShipmentOut,
    ShipmentUpdateRequest,
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
    "46b4f0d3-5708-11e9-9ff4-315000d079ad": ("Брюки, джинсы, бриджи, шорты муж", "men"),
    "7958c78e-9e44-11e9-9ff4-31500007d713": ("Трикотаж муж", "men"),
    "797d0e35-9e44-11e9-9ff4-31500007d733": ("Рубашки", "men"),
    "eec41100-9847-11eb-0a80-0616000ac009": ("Костюмы муж", "men"),
    "f8fae156-b37a-11e9-9ff4-3150003a11ec": ("Обувь муж", "men"),
    "0dea4445-f97a-11e9-0a80-0579004f5ecf": ("Верхняя одежда жен", "women"),
    "79292943-9e44-11e9-9ff4-31500007d6f3": ("Пиджаки, жакеты, бомбер жен", "women"),
    "f7b6946e-b37a-11e9-9ff4-3150003a0ff5": ("Футболки, поло, топы жен", "women"),
    "21e1d207-b53f-11e9-9ff4-31500015315b": ("Блузки, рубашки жен", "women"),
    "cd27a401-d3a6-11e9-0a80-02690003e199": ("Трикотаж жен", "women"),
    "78fabba1-9e44-11e9-9ff4-31500007d6c1": (
        "Брюки, джинсы, бриджи, шорты жен",
        "women",
    ),
    "26114fa1-a495-11e9-9ff4-3150000fa9a1": ("Платья, юбки жен", "women"),
    "79419e87-9e44-11e9-9ff4-31500007d6fe": ("Обувь жен", "women"),
    "82adf299-8e8b-11e9-9ff4-31500007fc47": ("Аксессуары", "unisex"),
}


def _money(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _canonical_ms_id(ms_id: str | None) -> str | None:
    if not ms_id:
        return ms_id
    return _CATEGORY_ALIAS_TO_CANONICAL_MS_ID.get(ms_id, ms_id)


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
    return [_category_out(row) for row in ordered] + passthrough


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
    row = Season(
        name=body.name.strip(),
        code=body.code.strip(),
        is_active=body.is_active,
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
        order.amount_eur = _money(sum((ln.amount_eur for ln in body.lines), ZERO))
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

"""Подарочные сертификаты через MCP закупок (те же правила, что REST /gift-certificates)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import AdminPrincipal
from app.mcp_procurement.registry import (
    SCOPE_WRITE,
    ToolArgumentError,
    check_limit,
    tool,
)
from app.models.gift_certificate import GiftCertificate
from app.routers import gift_certificates as gift_router
from app.schemas.gift_certificates import GiftCertificateCreate, GiftCertificateUpdate
from app.services.gift_certificates import certificate_link, phone_lookup_values, set_actual_status
from app.services.mcp_keys import McpActor

_MAX_LIST = 200
_MAX_BATCH = 150
_GIFT = AdminPrincipal(role="superuser", user=None)

_RECIPIENT = {
    "type": "object",
    "properties": {
        "phone": {"type": "string", "description": "Телефон владельца сертификата"},
        "name": {"type": "string", "description": "Имя владельца"},
        "last_name": {"type": "string", "description": "Фамилия владельца"},
        "description": {
            "type": "string",
            "description": "Комментарий к конкретному сертификату (если не задан — общий description)",
        },
    },
    "required": ["phone"],
}


def _dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    return str(detail)


def _cert_dict(cert: GiftCertificate) -> dict:
    return {
        "id": cert.id,
        "code": cert.code,
        "public_slug": cert.public_slug,
        "public_url": certificate_link(cert.public_slug),
        "nominal": cert.nominal,
        "amount": cert.amount,
        "description": cert.description,
        "employee": cert.employee,
        "check_amount": cert.check_amount,
        "status": cert.status,
        "created_at": cert.created_at.isoformat() if cert.created_at else None,
        "used_at": cert.used_at.isoformat() if cert.used_at else None,
        "indefinite": cert.indefinite,
        "period": cert.period,
        "name": cert.name,
        "last_name": cert.last_name,
        "phone": cert.phone,
        "giver_name": cert.giver_name,
        "giver_phone": cert.giver_phone,
    }


def _run(db: Session, fn, *args, **kwargs):
    kwargs["db"] = db
    if fn in (gift_router.create_certificate,):
        kwargs["principal"] = _GIFT
    elif fn in (
        gift_router.update_certificate,
        gift_router.list_certificates,
        gift_router.deliver_share_sms,
        gift_router.preview_share_sms,
    ):
        kwargs["_"] = _GIFT
    try:
        out = fn(*args, **kwargs)
        return _dump(out)
    except HTTPException as exc:
        db.rollback()
        raise ToolArgumentError(_detail(exc)) from exc


def _resolve_indefinite(indefinite: bool | None, period_days: int | None) -> tuple[bool, int | None]:
    if period_days is not None:
        if isinstance(period_days, bool) or not isinstance(period_days, int) or period_days < 1:
            raise ToolArgumentError("period_days должен быть целым >= 1")
        return False, period_days
    if indefinite is False:
        raise ToolArgumentError("Укажите period_days, если indefinite=false")
    return True, None


def _split_name(full: str | None) -> tuple[str | None, str | None]:
    if not full or not str(full).strip():
        return None, None
    parts = str(full).strip().split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


@tool(
    "list_gift_certificates",
    "Список подарочных сертификатов (новые сверху). Только чтение. "
    "Фильтр phone — нормализованный поиск по телефону владельца. "
    "Для массовой выдачи после создания смотрите create_gift_certificate и create_gift_certificates_batch.",
    {
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Только сертификаты на этот телефон"},
            "status": {
                "type": "string",
                "description": "ACTIVE, USED, EXPIRED или CANCELLED",
            },
            "limit": {
                "type": "integer",
                "description": f"1–{_MAX_LIST}, по умолчанию 50",
            },
        },
    },
)
def list_gift_certificates_tool(
    db: Session,
    actor: McpActor,
    phone: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> dict:
    del actor
    lim = check_limit(limit, _MAX_LIST)
    stmt = select(GiftCertificate).order_by(GiftCertificate.created_at.desc(), GiftCertificate.code.desc())
    if phone:
        values = phone_lookup_values(phone)
        if not values:
            raise ToolArgumentError("phone не похож на российский номер")
        stmt = stmt.where(GiftCertificate.phone.in_(values))
    if status:
        stmt = stmt.where(GiftCertificate.status == status.strip().upper())
    rows = db.scalars(stmt.limit(lim)).all()
    changed = False
    for cert in rows:
        if set_actual_status(cert):
            changed = True
    if changed:
        db.commit()
        for cert in rows:
            db.refresh(cert)
    return {"shown": len(rows), "items": [_cert_dict(c) for c in rows]}


@tool(
    "get_gift_certificate",
    "Один подарочный сертификат по id или public_slug. Только чтение.",
    {
        "type": "object",
        "properties": {
            "certificate_id": {
                "type": "string",
                "description": "id сертификата (ULID) или короткий public_slug из ссылки /c/…",
            },
        },
        "required": ["certificate_id"],
    },
)
def get_gift_certificate_tool(db: Session, actor: McpActor, certificate_id: str) -> dict:
    del actor
    key = (certificate_id or "").strip()
    if not key:
        raise ToolArgumentError("certificate_id обязателен")
    cert = db.get(GiftCertificate, key)
    if cert is None:
        cert = db.scalar(select(GiftCertificate).where(GiftCertificate.public_slug == key))
    if cert is None:
        raise ToolArgumentError("Сертификат не найден")
    if set_actual_status(cert):
        db.commit()
        db.refresh(cert)
    return _cert_dict(cert)


@tool(
    "create_gift_certificate",
    "Создать один подарочный сертификат (маркетинговый сценарий win-back и т.п.). "
    "Требует ключ с правом записи. "
    "Срок: передайте period_days (например 30) — тогда indefinite=false и действует period дней с created_at. "
    "После создания можно send_share_sms=true — SMS со ссылкой владельцу (как в UI сертификатов).",
    {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "nominal": {"type": "number", "description": "Номинал в рублях, например 5000"},
            "period_days": {
                "type": "integer",
                "description": "Срок действия в днях; при указании сертификат не бессрочный",
            },
            "indefinite": {
                "type": "boolean",
                "description": "true — бессрочно (period_days не нужен). По умолчанию true, если period_days не задан",
            },
            "name": {"type": "string"},
            "last_name": {"type": "string"},
            "description": {"type": "string", "description": "Комментарий / кампания, например «VIP потеряшки SMS»"},
            "employee": {"type": "string", "description": "Кто оформил; по умолчанию «MCP»"},
            "created_at": {"type": "string", "format": "date", "description": "YYYY-MM-DD, по умолчанию сегодня"},
            "send_share_sms": {
                "type": "boolean",
                "description": "Отправить SMS со ссылкой на сертификат после создания",
            },
        },
        "required": ["phone", "nominal"],
    },
    scope=SCOPE_WRITE,
)
def create_gift_certificate_tool(
    db: Session,
    actor: McpActor,
    phone: str,
    nominal: float,
    period_days: int | None = None,
    indefinite: bool | None = None,
    name: str | None = None,
    last_name: str | None = None,
    description: str | None = None,
    employee: str | None = None,
    created_at: str | None = None,
    send_share_sms: bool | None = None,
) -> dict:
    del actor
    if nominal < 0:
        raise ToolArgumentError("nominal не может быть отрицательным")
    ind, period = _resolve_indefinite(indefinite, period_days)
    created: date | None = None
    if created_at:
        try:
            created = date.fromisoformat(created_at)
        except ValueError as exc:
            raise ToolArgumentError("created_at должен быть YYYY-MM-DD") from exc
    body = GiftCertificateCreate(
        nominal=float(nominal),
        phone=phone.strip(),
        name=name,
        last_name=last_name,
        description=description or "",
        employee=(employee or "MCP").strip(),
        indefinite=ind,
        period=period,
        created_at=created,
        status="ACTIVE",
    )
    out = _run(db, gift_router.create_certificate, body=body)
    cert_id = out["id"]
    sms_result = None
    if send_share_sms:
        sms_result = _run(db, gift_router.deliver_share_sms, cert_id=cert_id)
    payload = {"certificate": out, "public_url": certificate_link(out["public_slug"])}
    if sms_result is not None:
        payload["share_sms"] = sms_result
    return payload


@tool(
    "create_gift_certificates_batch",
    "Массово создать сертификаты на список получателей (например VIP из Excel после SMS). "
    "Требует ключ с правом записи. "
    "Общие nominal, period_days и description применяются ко всем; у получателя можно переопределить description. "
    "Типичный win-back: nominal=5000, period_days=30, description «VIP потеряшки». "
    "При ошибке по одному номеру остальные всё равно создаются; смотрите errors.",
    {
        "type": "object",
        "properties": {
            "recipients": {
                "type": "array",
                "description": "Список получателей",
                "items": _RECIPIENT,
            },
            "nominal": {"type": "number"},
            "period_days": {"type": "integer", "description": "Срок в днях, например 30"},
            "indefinite": {"type": "boolean"},
            "description": {"type": "string"},
            "employee": {"type": "string"},
            "send_share_sms": {
                "type": "boolean",
                "description": "SMS со ссылкой каждому после успешного создания",
            },
        },
        "required": ["recipients", "nominal"],
    },
    scope=SCOPE_WRITE,
)
def create_gift_certificates_batch_tool(
    db: Session,
    actor: McpActor,
    recipients: list,
    nominal: float,
    period_days: int | None = None,
    indefinite: bool | None = None,
    description: str | None = None,
    employee: str | None = None,
    send_share_sms: bool | None = None,
) -> dict:
    del actor
    if not isinstance(recipients, list) or not recipients:
        raise ToolArgumentError("recipients — непустой массив")
    if len(recipients) > _MAX_BATCH:
        raise ToolArgumentError(f"Не больше {_MAX_BATCH} получателей за один вызов")
    if nominal < 0:
        raise ToolArgumentError("nominal не может быть отрицательным")
    ind, period = _resolve_indefinite(indefinite, period_days)
    emp = (employee or "MCP").strip()
    base_desc = description or ""
    created_items: list[dict] = []
    errors: list[dict] = []
    for idx, raw in enumerate(recipients):
        if not isinstance(raw, dict):
            errors.append({"index": idx, "error": "элемент recipients должен быть объектом"})
            continue
        phone = str(raw.get("phone") or "").strip()
        if not phone:
            errors.append({"index": idx, "error": "нет phone"})
            continue
        name = raw.get("name")
        last_name = raw.get("last_name")
        if name and not last_name and isinstance(name, str) and " " in name.strip():
            name, last_name = _split_name(name)
        desc = str(raw.get("description") or base_desc)
        body = GiftCertificateCreate(
            nominal=float(nominal),
            phone=phone,
            name=name,
            last_name=last_name,
            description=desc,
            employee=emp,
            indefinite=ind,
            period=period,
            status="ACTIVE",
        )
        try:
            out = _run(db, gift_router.create_certificate, body=body)
        except ToolArgumentError as exc:
            errors.append({"index": idx, "phone": phone, "error": str(exc)})
            continue
        item = {
            "index": idx,
            "phone": phone,
            "certificate": out,
            "public_url": certificate_link(out["public_slug"]),
        }
        if send_share_sms:
            try:
                item["share_sms"] = _run(db, gift_router.deliver_share_sms, cert_id=out["id"])
            except ToolArgumentError as exc:
                item["share_sms_error"] = str(exc)
        created_items.append(item)
    return {
        "created_count": len(created_items),
        "error_count": len(errors),
        "items": created_items,
        "errors": errors,
    }


@tool(
    "update_gift_certificate",
    "Изменить сертификат (остаток, телефон, срок, описание). Требует ключ с правом записи.",
    {
        "type": "object",
        "properties": {
            "certificate_id": {"type": "string"},
            "amount": {"type": "number", "description": "Новый остаток"},
            "phone": {"type": "string"},
            "name": {"type": "string"},
            "last_name": {"type": "string"},
            "description": {"type": "string"},
            "indefinite": {"type": "boolean"},
            "period": {"type": "integer", "description": "Дней действия, если не бессрочный"},
        },
        "required": ["certificate_id"],
    },
    scope=SCOPE_WRITE,
)
def update_gift_certificate_tool(
    db: Session,
    actor: McpActor,
    certificate_id: str,
    amount: float | None = None,
    phone: str | None = None,
    name: str | None = None,
    last_name: str | None = None,
    description: str | None = None,
    indefinite: bool | None = None,
    period: int | None = None,
) -> dict:
    del actor
    cid = (certificate_id or "").strip()
    if not cid:
        raise ToolArgumentError("certificate_id обязателен")
    patch = GiftCertificateUpdate(
        amount=amount,
        phone=phone,
        name=name,
        last_name=last_name,
        description=description,
        indefinite=indefinite,
        period=period,
    )
    return _run(db, gift_router.update_certificate, cert_id=cid, body=patch)


@tool(
    "send_gift_certificate_share_sms",
    "Отправить владельцу SMS со ссылкой на сертификат (как кнопка в интерфейсе). "
    "Требует ключ с правом записи. Сертификат должен быть ACTIVE.",
    {
        "type": "object",
        "properties": {
            "certificate_id": {"type": "string"},
        },
        "required": ["certificate_id"],
    },
    scope=SCOPE_WRITE,
)
def send_gift_certificate_share_sms_tool(
    db: Session, actor: McpActor, certificate_id: str
) -> dict:
    del actor
    cid = (certificate_id or "").strip()
    if not cid:
        raise ToolArgumentError("certificate_id обязателен")
    return _run(db, gift_router.deliver_share_sms, cert_id=cid)

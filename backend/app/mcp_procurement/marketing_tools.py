"""Маркетинг PWA: акция welcome-gift, промо-модалка и hero на главной."""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import AdminPrincipal
from app.mcp_procurement.registry import SCOPE_WRITE, ToolArgumentError, tool
from app.models.hero_banner import HeroBanner
from app.models.promo_banner import PromoBanner
from app.routers import admin_hero_banners, admin_promo_banners, admin_welcome_gift
from app.schemas.hero_banner import AdminHeroBannerCreateRequest, AdminHeroBannerUpdateRequest
from app.schemas.promo_banner import AdminPromoBannerCreateRequest, AdminPromoBannerUpdateRequest
from app.schemas.welcome_gift import WelcomeGiftSettingsPut
from app.services.hero_banner_storage import delete_hero_banner_image, save_hero_banner_image
from app.services.mcp_keys import McpActor
from app.services.promo_banner_storage import delete_promo_banner_image, save_promo_banner_image

_ADS = AdminPrincipal(role="superuser", user=None)
_UUID = {"type": "string", "format": "uuid"}
_DATE = {"type": "string", "format": "date"}
_DATETIME = {
    "type": "string",
    "description": "ISO 8601, например 2026-10-21T09:00:00+03:00",
}
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
_DISPLAY_MODES = {
    "type": "string",
    "enum": ["once", "twice", "every_visit"],
    "description": "once — один раз; twice — два; every_visit — не чаще раза в 2 часа",
}
_IMAGE_FIT = {"type": "string", "enum": ["fit", "cover"]}


def _dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    return str(detail)


def _run(db: Session, fn, *args, **kwargs):
    kwargs["db"] = db
    if fn in (admin_welcome_gift.get_welcome_gift_settings,):
        kwargs["_"] = _ADS
    else:
        kwargs["_su"] = _ADS
    try:
        return _dump(fn(*args, **kwargs))
    except HTTPException as exc:
        db.rollback()
        raise ToolArgumentError(_detail(exc)) from exc


def _uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


def _parse_dt(value: str | None, name: str) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolArgumentError(f"{name}: ожидается ISO-дата/время") from exc


def _decode_image(content_base64: str, filename: str, max_bytes: int) -> tuple[str, bytes]:
    raw = (content_base64 or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolArgumentError("content_base64: неверная base64-строка") from exc
    if len(data) > max_bytes:
        raise ToolArgumentError(
            f"Файл больше {max_bytes // (1024 * 1024)} МБ — уменьшите или загрузите через админку"
        )
    ext = Path(filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise ToolArgumentError(
            f"filename: допустимые расширения {', '.join(sorted(_ALLOWED_EXT))}"
        )
    return ext, data


# --- Welcome gift ----------------------------------------------------------


@tool(
    "get_welcome_gift_settings",
    "Акция «сертификат за приложение»: включена ли, период, номинал и срок действия "
    "сертификата в днях. Сертификат выдаётся один раз: регистрация в период акции, "
    "открытие установленного PWA и активная push-подписка.",
    {"type": "object", "properties": {}, "required": []},
)
def get_welcome_gift_settings(db: Session, _actor: McpActor):
    return _run(db, admin_welcome_gift.get_welcome_gift_settings)


@tool(
    "update_welcome_gift_settings",
    "Включить или изменить акцию welcome-gift. При enabled=true нужны valid_from и nominal>0. "
    "valid_to пустой — без даты окончания. period_days — срок жизни сертификата (обычно 30).",
    {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "valid_from": {**_DATE, "description": "С какой даты (МСК) считаются новые регистрации"},
            "valid_to": _DATE,
            "nominal": {"type": "number", "description": "Номинал сертификата, ₽"},
            "period_days": {"type": "integer", "description": "Срок действия сертификата, дней"},
        },
        "required": ["enabled", "nominal", "period_days"],
    },
    scope=SCOPE_WRITE,
)
def update_welcome_gift_settings(
    db: Session,
    _actor: McpActor,
    *,
    enabled: bool,
    nominal: float,
    period_days: int,
    valid_from: str | None = None,
    valid_to: str | None = None,
):
    body = WelcomeGiftSettingsPut(
        enabled=enabled,
        valid_from=valid_from,
        valid_to=valid_to,
        nominal=nominal,
        period_days=period_days,
    )
    return _run(db, admin_welcome_gift.put_welcome_gift_settings, body=body)


# --- Promo modal -----------------------------------------------------------


@tool(
    "list_promo_banners",
    "Промо-модалка на главной PWA: заголовок, текст (**жирный**), картинка, ссылка, "
    "кнопки «муж/жен» в коллекции, расписание и режим показа.",
    {"type": "object", "properties": {}, "required": []},
)
def list_promo_banners(db: Session, _actor: McpActor):
    return _run(db, admin_promo_banners.list_promo_banners)


@tool(
    "get_promo_banner",
    "Один промо-баннер по id (из list_promo_banners).",
    {
        "type": "object",
        "properties": {"banner_id": _UUID},
        "required": ["banner_id"],
    },
)
def get_promo_banner(db: Session, _actor: McpActor, *, banner_id: str):
    row = db.get(PromoBanner, _uuid(banner_id, "banner_id"))
    if row is None:
        raise ToolArgumentError("Баннер не найден")
    from app.schemas.promo_banner import AdminPromoBannerOut

    return _dump(AdminPromoBannerOut.model_validate(row))


@tool(
    "create_promo_banner",
    "Создать промо-модалку. Картинку потом — upload_promo_banner_image или админка «Реклама». "
    "show_gender_ctas=true — две кнопки в /swipe/male и /swipe/female. "
    "link_url — внешняя ссылка «Подробнее» (внутренние пути приложения не открываются).",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string", "description": "Текст; **фраза** для жирного"},
            "image_fit": _IMAGE_FIT,
            "link_url": {"type": "string"},
            "link_label": {"type": "string"},
            "show_gender_ctas": {"type": "boolean"},
            "cta_male_label": {"type": "string"},
            "cta_female_label": {"type": "string"},
            "starts_at": _DATETIME,
            "ends_at": _DATETIME,
            "display_mode": _DISPLAY_MODES,
            "is_active": {"type": "boolean"},
            "priority": {"type": "integer", "description": "Выше — чаще побеждает при нескольких"},
        },
        "required": ["title"],
    },
    scope=SCOPE_WRITE,
)
def create_promo_banner(db: Session, _actor: McpActor, *, title: str, **fields):
    body = AdminPromoBannerCreateRequest.model_validate({"title": title, **fields})
    return _run(db, admin_promo_banners.create_promo_banner, body=body)


@tool(
    "update_promo_banner",
    "Изменить промо-модалку (в т.ч. is_active). clear_image=true удалит файл картинки.",
    {
        "type": "object",
        "properties": {
            "banner_id": _UUID,
            "title": {"type": "string"},
            "body": {"type": "string"},
            "image_fit": _IMAGE_FIT,
            "link_url": {"type": "string"},
            "link_label": {"type": "string"},
            "show_gender_ctas": {"type": "boolean"},
            "cta_male_label": {"type": "string"},
            "cta_female_label": {"type": "string"},
            "starts_at": _DATETIME,
            "ends_at": _DATETIME,
            "display_mode": _DISPLAY_MODES,
            "is_active": {"type": "boolean"},
            "priority": {"type": "integer"},
            "clear_image": {"type": "boolean"},
        },
        "required": ["banner_id"],
    },
    scope=SCOPE_WRITE,
)
def update_promo_banner(db: Session, _actor: McpActor, *, banner_id: str, **fields):
    body = AdminPromoBannerUpdateRequest.model_validate(fields)
    return _run(
        db,
        admin_promo_banners.update_promo_banner,
        banner_id=_uuid(banner_id, "banner_id"),
        body=body,
    )


@tool(
    "upload_promo_banner_image",
    "Загрузить картинку промо-модалки: base64 и имя файла с расширением (.webp, .jpg…). "
    "Альтернатива — файл в админке после create_promo_banner.",
    {
        "type": "object",
        "properties": {
            "banner_id": _UUID,
            "filename": {"type": "string", "description": "Например promo-gift.webp"},
            "content_base64": {"type": "string", "description": "Содержимое файла в base64"},
        },
        "required": ["banner_id", "filename", "content_base64"],
    },
    scope=SCOPE_WRITE,
)
def upload_promo_banner_image_mcp(
    db: Session,
    _actor: McpActor,
    *,
    banner_id: str,
    filename: str,
    content_base64: str,
):
    bid = _uuid(banner_id, "banner_id")
    row = db.get(PromoBanner, bid)
    if row is None:
        raise ToolArgumentError("Баннер не найден")
    ext, data = _decode_image(content_base64, filename, settings.promo_banner_max_file_bytes)
    if row.image_url:
        delete_promo_banner_image(row.image_url)
    url = save_promo_banner_image(bid, ext, data)
    row.image_url = url
    db.commit()
    db.refresh(row)
    from app.schemas.promo_banner import AdminPromoBannerOut

    return _dump(AdminPromoBannerOut.model_validate(row))


# --- Hero carousel ---------------------------------------------------------


@tool(
    "list_hero_banners",
    "Hero-карусель на главной: mobile и desktop-картинки, подписи, одна CTA-ссылка "
    "(можно /swipe/male или /swipe/female).",
    {"type": "object", "properties": {}, "required": []},
)
def list_hero_banners(db: Session, _actor: McpActor):
    return _run(db, admin_hero_banners.list_hero_banners)


@tool(
    "get_hero_banner",
    "Один hero-баннер по id.",
    {
        "type": "object",
        "properties": {"banner_id": _UUID},
        "required": ["banner_id"],
    },
)
def get_hero_banner(db: Session, _actor: McpActor, *, banner_id: str):
    row = db.get(HeroBanner, _uuid(banner_id, "banner_id"))
    if row is None:
        raise ToolArgumentError("Баннер не найден")
    from app.schemas.hero_banner import AdminHeroBannerOut

    return _dump(AdminHeroBannerOut.model_validate(row))


@tool(
    "create_hero_banner",
    "Создать слайд hero. Картинки — upload_hero_banner_image (variant mobile/desktop).",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "body": {"type": "string"},
            "link_url": {
                "type": "string",
                "description": "Внутренний путь, напр. /swipe/female или внешний URL",
            },
            "link_label": {"type": "string"},
            "starts_at": _DATETIME,
            "ends_at": _DATETIME,
            "is_active": {"type": "boolean"},
            "priority": {"type": "integer"},
        },
        "required": ["title"],
    },
    scope=SCOPE_WRITE,
)
def create_hero_banner(db: Session, _actor: McpActor, *, title: str, **fields):
    cleaned = {k: v for k, v in fields.items() if v is not None}
    if "starts_at" in cleaned:
        cleaned["starts_at"] = _parse_dt(cleaned["starts_at"], "starts_at")
    if "ends_at" in cleaned:
        cleaned["ends_at"] = _parse_dt(cleaned["ends_at"], "ends_at")
    body = AdminHeroBannerCreateRequest.model_validate({"title": title, **cleaned})
    return _run(db, admin_hero_banners.create_hero_banner, body=body)


@tool(
    "update_hero_banner",
    "Изменить hero-слайд.",
    {
        "type": "object",
        "properties": {
            "banner_id": _UUID,
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "body": {"type": "string"},
            "link_url": {"type": "string"},
            "link_label": {"type": "string"},
            "starts_at": _DATETIME,
            "ends_at": _DATETIME,
            "is_active": {"type": "boolean"},
            "priority": {"type": "integer"},
            "clear_image": {"type": "boolean"},
            "clear_image_desktop": {"type": "boolean"},
        },
        "required": ["banner_id"],
    },
    scope=SCOPE_WRITE,
)
def update_hero_banner(db: Session, _actor: McpActor, *, banner_id: str, **fields):
    cleaned = dict(fields)
    if cleaned.get("starts_at") is not None:
        cleaned["starts_at"] = _parse_dt(cleaned["starts_at"], "starts_at")
    if cleaned.get("ends_at") is not None:
        cleaned["ends_at"] = _parse_dt(cleaned["ends_at"], "ends_at")
    body = AdminHeroBannerUpdateRequest.model_validate(cleaned)
    return _run(
        db,
        admin_hero_banners.update_hero_banner,
        banner_id=_uuid(banner_id, "banner_id"),
        body=body,
    )


@tool(
    "upload_hero_banner_image",
    "Картинка hero: variant mobile (телефон) или desktop (широкий экран).",
    {
        "type": "object",
        "properties": {
            "banner_id": _UUID,
            "filename": {"type": "string"},
            "content_base64": {"type": "string"},
            "variant": {
                "type": "string",
                "enum": ["mobile", "desktop"],
                "description": "mobile — основная; desktop — для экранов от 768px",
            },
        },
        "required": ["banner_id", "filename", "content_base64"],
    },
    scope=SCOPE_WRITE,
)
def upload_hero_banner_image_mcp(
    db: Session,
    _actor: McpActor,
    *,
    banner_id: str,
    filename: str,
    content_base64: str,
    variant: str = "mobile",
):
    if variant not in ("mobile", "desktop"):
        raise ToolArgumentError("variant: mobile или desktop")
    bid = _uuid(banner_id, "banner_id")
    row = db.get(HeroBanner, bid)
    if row is None:
        raise ToolArgumentError("Баннер не найден")
    ext, data = _decode_image(content_base64, filename, settings.hero_banner_max_file_bytes)
    if variant == "mobile" and row.image_url:
        delete_hero_banner_image(row.image_url)
    if variant == "desktop" and row.image_url_desktop:
        delete_hero_banner_image(row.image_url_desktop)
    url = save_hero_banner_image(bid, ext, data, variant=variant)
    if variant == "desktop":
        row.image_url_desktop = url
    else:
        row.image_url = url
    db.commit()
    db.refresh(row)
    from app.schemas.hero_banner import AdminHeroBannerOut

    return _dump(AdminHeroBannerOut.model_validate(row))

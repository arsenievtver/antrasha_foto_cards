"""Правила сертификатов из wizard: статус, код AN-######, маскировка, SMS МТС, Telegram."""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import requests
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.gift_certificate import (
    GiftCertificate,
    GiftCertificateStatus,
    GiftCertificateTransaction,
    GiftTransactionStatus,
)

log = logging.getLogger("app.gift_certificates")

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_MTS_BASE = "https://omnichannel.mts.ru"
_SMS_TEMPLATE = (
    "Для списания на сумму {charge_sum} рублей по вашему подарочному сертификату {cert_code} "
    "назовите оператору код подтверждения {confirm_code}."
)
_TELEGRAM_TEMPLATE = """🎁<b>Подарочный сертификат ANTRASHA оформлен</b>
Сертификат даёт право на скидку в размере номинала при покупке в магазине ANTRASHA.

<b>Номер сертификата:</b> <code>{cert_code}</code>
<b>Номинал:</b> <code>{amount} </code>
<b>Тел владельца:</b> {phone}
<b>Срок действия:</b> {expire_date}

🔗 <b>Ссылка на сертификат:</b>
{link}
<i>По ссылке доступен статус сертификата и полные условия использования.</i>

Вы можете переслать это сообщение получателю — ссылка является сертификатом.

📍 <b>Магазин ANTRASHA</b>
г. Тверь, б-р Радищева, 37
https://antrasha.ru/

ℹ️ <b>Правила использования:</b>
https://antrasha.ru/giftcards
Если возникнут вопросы — мы всегда на связи:
Наш канал: https://t.me/+iw9aML3TIEJmOTFi
Наш бот: https://t.me/AntrashaBot
"""


def new_ulid() -> str:
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    randomness = int.from_bytes(os.urandom(10), "big")
    value = (timestamp_ms << 80) | randomness
    chars = [""] * 26
    for index in range(25, -1, -1):
        chars[index] = _ULID_ALPHABET[value & 31]
        value >>= 5
    return "".join(chars)


_SLUG_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_SLUG_LENGTH = 7


def allocate_code(db: Session) -> str:
    number = db.execute(text("SELECT nextval('gift_certificate_code_seq')")).scalar_one()
    return f"AN-{int(number):06d}"


def allocate_public_slug(db: Session) -> str:
    for _ in range(8):
        slug = "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(_SLUG_LENGTH))
        taken = db.scalar(select(GiftCertificate.id).where(GiftCertificate.public_slug == slug))
        if taken is None:
            return slug
    raise RuntimeError("Не удалось выделить короткую ссылку")


def generate_confirm_code(length: int = 4) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def is_expired(cert: GiftCertificate, today: date | None = None) -> bool:
    if cert.indefinite:
        return False
    if cert.created_at is None or not cert.period:
        return False
    deadline = cert.created_at + timedelta(days=cert.period)
    return (today or date.today()) >= deadline


def set_actual_status(cert: GiftCertificate, today: date | None = None) -> bool:
    if cert.status in (
        GiftCertificateStatus.CANCELLED.value,
        GiftCertificateStatus.USED.value,
    ):
        return False
    initial = cert.status
    if is_expired(cert, today):
        cert.status = GiftCertificateStatus.EXPIRED.value
    else:
        cert.status = GiftCertificateStatus.ACTIVE.value
    if cert.amount <= 0:
        cert.status = GiftCertificateStatus.USED.value
        cert.used_at = today or date.today()
    return cert.status != initial


def hide_phone(phone: str | None) -> str:
    raw = (phone or "").strip()
    if len(raw) <= 3:
        return raw
    return "*" * (len(raw) - 3) + raw[-3:]


def hide_name(value: str | None) -> str | None:
    if not value:
        return None
    return value[0] + "******"


def expire_open_transactions(db: Session, cert: GiftCertificate) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.gift_confirm_minutes)
    rows = db.scalars(
        select(GiftCertificateTransaction).where(
            GiftCertificateTransaction.cert_id == cert.id,
            GiftCertificateTransaction.status == GiftTransactionStatus.OPENED.value,
        )
    ).all()
    for tran in rows:
        moment = tran.time
        if moment is not None and moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if moment is not None and moment < cutoff:
            tran.status = GiftTransactionStatus.CANCELLED.value
            if cert.actual_tran_id == tran.id:
                cert.actual_tran_id = None


def certificate_link(slug: str) -> str:
    base = (settings.public_giftcard_url or "").rstrip("/")
    return f"{base}/c/{slug}"


def telegram_text(cert: GiftCertificate) -> str:
    if cert.indefinite or cert.created_at is None or not cert.period:
        expire = "неограничен"
    else:
        expire = (cert.created_at + timedelta(days=cert.period)).strftime("%Y-%m-%d")
    return _TELEGRAM_TEMPLATE.format(
        cert_code=cert.code,
        amount=cert.amount,
        phone=hide_phone(cert.phone),
        expire_date=expire,
        link=certificate_link(cert.public_slug),
    )


def _mts_phone(phone: str) -> str:
    raw = phone.strip()
    if raw.startswith("+7"):
        return raw[1:]
    if raw.startswith("8") and len(raw) >= 11:
        return "7" + raw[1:]
    if raw.startswith("7"):
        return raw
    raise ValueError("Некорректный телефон для SMS")


def _owner_label(cert: GiftCertificate) -> str:
    parts = [part.strip() for part in (cert.name, cert.last_name) if part and part.strip()]
    return " ".join(parts)


def share_sms_messages(cert: GiftCertificate) -> list[dict]:
    link = certificate_link(cert.public_slug)
    giver = (cert.giver_name or "").strip()
    giver_phone = (cert.giver_phone or "").strip()
    owner = _owner_label(cert)
    messages = []
    if giver:
        messages.append(
            {
                "role": "owner",
                "phone": cert.phone,
                "text": f"{giver} дарит вам сертификат ANTRASHA: {link}",
            }
        )
        if giver_phone:
            target = f" для {owner}" if owner else ""
            messages.append(
                {
                    "role": "giver",
                    "phone": giver_phone,
                    "text": f"Вы оформили сертификат ANTRASHA{target}. Поделиться можно ссылкой: {link}",
                }
            )
    else:
        messages.append(
            {
                "role": "owner",
                "phone": cert.phone,
                "text": f"Вам оформлен сертификат ANTRASHA: {link}",
            }
        )
    return messages


def _post_mts_sms(phone: str, text: str) -> tuple[str | None, bool, str | None]:
    if not settings.mts_sms_enabled:
        log.info("SMS выключена, текст для %s: %s", phone, text)
        return f"test_{uuid.uuid4()}", True, None
    if not settings.mts_login or not settings.mts_password or not settings.mts_name:
        return None, False, "SMS МТС не настроена"
    try:
        msisdn = _mts_phone(phone)
    except ValueError as exc:
        return None, False, str(exc)
    try:
        response = requests.post(
            f"{_MTS_BASE}/http-api/v1/messages",
            json={
                "messages": [
                    {
                        "content": {"short_text": text},
                        "from": {"sms_address": settings.mts_name},
                        "to": [{"msisdn": msisdn}],
                    }
                ]
            },
            auth=(settings.mts_login, settings.mts_password),
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, False, str(exc)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    message_id = None
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if isinstance(messages, list) and messages:
        message_id = messages[0].get("internal_id")
    if response.status_code >= 400 or not message_id:
        return None, False, f"МТС HTTP {response.status_code}"
    return str(message_id), True, None


def send_confirm_sms(cert: GiftCertificate, charge_sum: float, confirm_code: str) -> tuple[str | None, bool, str | None]:
    text = _SMS_TEMPLATE.format(
        charge_sum=charge_sum,
        cert_code=cert.code,
        confirm_code=confirm_code,
    )
    return _post_mts_sms(cert.phone, text)


def send_share_sms(cert: GiftCertificate) -> list[dict]:
    sent = []
    for item in share_sms_messages(cert):
        sms_id, sms_sent, sms_error = _post_mts_sms(item["phone"], item["text"])
        sent.append({**item, "sms_id": sms_id, "sent": sms_sent, "error": sms_error})
    return sent


def send_telegram(chat_id: int, text: str, image_url: str | None) -> None:
    token = (settings.telegram_token or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN не задан")
    photo = (image_url or "").strip() or settings.telegram_default_image_url
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            json={
                "chat_id": chat_id,
                "photo": photo,
                "caption": text,
                "parse_mode": "HTML",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(str(exc)) from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400 or not payload.get("ok", False):
        description = payload.get("description") if isinstance(payload, dict) else response.text
        raise RuntimeError(description or f"Telegram HTTP {response.status_code}")

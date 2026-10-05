"""Пакетная рассылка произвольного текста через SMS МТС."""

from __future__ import annotations

import time

from app.services.gift_certificates import send_text_sms
from app.utils.phone import normalize_ru_phone

MAX_PHONES = 150
MAX_TEXT_LEN = 1000
DEFAULT_PAUSE_SEC = 8.0


def deliver_marketing_sms_batch(
    *,
    phones: list[str],
    text: str,
    pause_seconds: float = DEFAULT_PAUSE_SEC,
    dry_run: bool = False,
) -> dict:
    body = (text or "").strip()
    if not body:
        raise ValueError("text не может быть пустым")
    if len(body) > MAX_TEXT_LEN:
        raise ValueError(f"text длиннее {MAX_TEXT_LEN} символов")
    if not phones:
        raise ValueError("phones — непустой список")
    if len(phones) > MAX_PHONES:
        raise ValueError(f"Не больше {MAX_PHONES} номеров за один вызов")
    if pause_seconds < 0 or pause_seconds > 60:
        raise ValueError("pause_seconds от 0 до 60")

    items: list[dict] = []
    errors: list[dict] = []
    for idx, raw in enumerate(phones):
        phone = normalize_ru_phone(str(raw or "").strip())
        if not phone:
            errors.append({"index": idx, "phone": raw, "error": "некорректный телефон"})
            continue
        if dry_run:
            items.append({"index": idx, "phone": phone, "sent": True, "dry_run": True})
        else:
            result = send_text_sms(phone, body)
            row = {"index": idx, **result}
            items.append(row)
            if not result.get("sent"):
                errors.append(
                    {"index": idx, "phone": phone, "error": result.get("error") or "не отправлено"},
                )
        if not dry_run and pause_seconds and idx + 1 < len(phones):
            time.sleep(pause_seconds)

    sent_count = sum(1 for i in items if i.get("sent"))
    return {
        "dry_run": dry_run,
        "text_length": len(body),
        "pause_seconds": pause_seconds,
        "total": len(phones),
        "sent_count": sent_count,
        "error_count": len(errors),
        "items": items,
        "errors": errors,
    }

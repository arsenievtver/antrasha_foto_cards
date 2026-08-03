"""Права сотрудников админки (роль worker). Суперпользователь имеет все права."""

from __future__ import annotations

# Ключ → подпись в UI. Совпадает с группами меню.
ADMIN_PERMISSIONS: dict[str, str] = {
    "stats": "Обзор",
    "clients": "Клиенты",
    "photos": "Фото",
    "ads": "Реклама",
    "product": "Товар",
    "outlet": "Аутлет: фото",
    "outlet_transfer": "Аутлет: перенос",
    "ai_assistant": "AI помощник",
}

ADMIN_PERMISSION_KEYS: frozenset[str] = frozenset(ADMIN_PERMISSIONS)
DEFAULT_WORKER_PERMISSIONS: list[str] = ["photos"]


def normalize_permissions(raw: object | None) -> list[str]:
    if not raw:
        return []
    if not isinstance(raw, (list, tuple, set)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = str(item).strip()
        if key in ADMIN_PERMISSION_KEYS and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def effective_worker_permissions(raw: object | None) -> list[str]:
    """Если у сотрудника прав ещё нет (старые записи) — даём доступ к Фото."""
    perms = normalize_permissions(raw)
    return perms if perms else list(DEFAULT_WORKER_PERMISSIONS)

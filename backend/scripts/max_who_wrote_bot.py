#!/usr/bin/env python3
"""Кто писал боту: user_id для MAX_NOTIFY_USER_ID. Сначала отправьте боту сообщение из MAX."""

from __future__ import annotations

from app.services.max_notify import list_recent_max_sender_user_ids


def main() -> None:
    status, ids, marker = list_recent_max_sender_user_ids(limit=50)
    print("updates_http_status=", status)
    print("marker=", marker)
    if status != 200:
        raise SystemExit(1)
    if not ids:
        print(
            "human user_id не найдены. Напишите боту с телефона (тест) и запустите скрипт снова."
        )
        raise SystemExit(2)
    print("candidate MAX_NOTIFY_USER_ID values (люди, не боты):")
    for uid in sorted(ids):
        print(f"  {uid}")


if __name__ == "__main__":
    main()

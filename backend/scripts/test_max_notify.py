#!/usr/bin/env python3
"""Диагностика MAX Bot API из контейнера backend: PYTHONPATH=/app python scripts/test_max_notify.py"""

from __future__ import annotations

from app.config import settings
from app.services.max_notify import max_notify_configured, probe_max_bot_api


def main() -> None:
    print("max_notify_configured=", max_notify_configured())
    uid = settings.max_notify_user_id
    print("max_notify_user_id=", uid)
    ok, msg = probe_max_bot_api()
    print("probe_max_bot_api=", ok, msg)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""HTTPS к web.push.apple.com: default requests vs IPv4-session (как Avtomedik external_http).

На сервере (не на хосте — там часто нет python):

  cd /opt/antrasha_tinder/deploy
  docker compose -f docker-compose.prod.yml exec backend python scripts/diag_push_http.py

Локально в образе backend: python scripts/diag_push_http.py (WORKDIR /app).
"""

from __future__ import annotations

from app.services.web_push import probe_push_transport


def main() -> None:
    rows = probe_push_transport()
    print("URL https://web.push.apple.com/ (GET, не push POST — только connect/TLS/ответ)")
    for row in rows:
        err = row.get("error")
        status = row.get("status")
        extra = f" status={status}" if status is not None else ""
        if err:
            extra = f" error={err}"
        print(f"  {row['variant']}: {row['seconds']} s{extra}")
    cold = float(rows[0]["seconds"])
    ipv4_cold = float(rows[1]["seconds"])
    if cold > 2.0 and ipv4_cold < 1.0:
        print(
            "\nПохоже на IPv6/anycast cold connect: default requests медленный, "
            "IPv4-session быстрый — после деплоя web_push первый push должен проходить с первого раза."
        )


if __name__ == "__main__":
    main()

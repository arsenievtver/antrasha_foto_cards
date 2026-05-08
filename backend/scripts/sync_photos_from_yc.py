"""
CLI: синхронизация фото из Yandex Object Storage → Postgres.

Логика в app/services/yc_photo_sync.py (та же, что у API и фонового цикла).

Запуск из каталога backend:
  PYTHONPATH=. .venv/bin/python scripts/sync_photos_from_yc.py

Переменные — см. корневой .env.example (YC_S3_*, бакеты).

После импорта по умолчанию для каждого поля отключаются активные фото в БД,
чьих URL нет в текущем списке объектов бакета. --keep-orphans отключает это.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import engine
from app.services.yc_photo_sync import run_sync_job_commit


def _database_url_safe() -> str:
    u = make_url(settings.database_url)
    return u.render_as_string(hide_password=True)


def require_postgres() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as e:
        print(
            "Ошибка: не удаётся подключиться к PostgreSQL.\n"
            f"  DATABASE_URL (без пароля): {_database_url_safe()}\n"
            "Запустите контейнер с БД или локальный Postgres.",
            file=sys.stderr,
        )
        raise SystemExit(1) from e


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт фото из Yandex Object Storage в Postgres.")
    parser.add_argument(
        "--keep-orphans",
        action="store_true",
        help="Не отключать записи в БД для этого пола, если их URL нет в бакете",
    )
    args = parser.parse_args()

    if not settings.yc_s3_configured:
        print(
            "Ошибка: в .env не заданы YC_S3_ACCESS_KEY_ID и YC_S3_SECRET_ACCESS_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)

    require_postgres()

    clean = not args.keep_orphans
    try:
        out = run_sync_job_commit(settings, deactivate_not_in_bucket=clean)
    except Exception:
        raise
    m, f = out["male"], out["female"]
    print(
        f"OK: male — объектов в бакете {m['keys_in_bucket']}, добавлено строк {m['rows_added']}, "
        f"деактивировано лишних {m['rows_deactivated']}; "
        f"female — в бакете {f['keys_in_bucket']}, добавлено {f['rows_added']}, "
        f"деактивировано {f['rows_deactivated']}."
    )


if __name__ == "__main__":
    main()

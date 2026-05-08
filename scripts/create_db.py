#!/usr/bin/env python3
"""
Создание роли и БД под приложение (подключение от суперпользователя Postgres).
Вызывается из db-init.sh при заданных POSTGRES_SUPERUSER / POSTGRES_SUPERUSER_PASSWORD.
"""
from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql


def main() -> int:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    superuser = os.environ.get("POSTGRES_SUPERUSER", "").strip()
    super_pw = os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "")
    app_user = os.environ.get("POSTGRES_APP_USER", "antrasha")
    app_pw = os.environ.get("POSTGRES_APP_PASSWORD", "antrasha")
    app_db = os.environ.get("POSTGRES_APP_DB", "antrasha")

    if not superuser:
        print("[create_db] POSTGRES_SUPERUSER пуст — выход")
        return 0

    conninfo = (
        f"host={host} port={port} dbname=postgres user={superuser} password={super_pw}"
    )
    try:
        with psycopg.connect(conninfo, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s",
                    (app_user,),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(
                            sql.Identifier(app_user),
                        ),
                        (app_pw,),
                    )
                    print(f"[create_db] создан пользователь {app_user}")
                else:
                    print(f"[create_db] пользователь {app_user} уже существует")

                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (app_db,),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(app_db),
                            sql.Identifier(app_user),
                        )
                    )
                    print(f"[create_db] создана база {app_db}")
                else:
                    print(f"[create_db] база {app_db} уже существует")
    except Exception as e:
        print(f"[create_db] ошибка: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

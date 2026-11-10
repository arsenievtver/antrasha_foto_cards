"""
AI-ingest worker entry point.

Usage:
    python -m jobs.ai_ingest_worker

Starts N concurrent slots (AI_INGEST_WORKER_CONCURRENCY), each continuously
pulling pending jobs from the DB and processing them via the Fashn API.
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy.exc import ProgrammingError

from app.config import settings
from app.database import SessionLocal
from app.logging_config import setup_logging
from app.services.ai_ingest_worker import (
    embed_one_draft_photo,
    reset_stale_processing_jobs,
    try_process_one_ingest_job,
)
from app.services.outlet_photo_jobs import reset_running_jobs, try_process_one_outlet_photo_job
from app.services.photo_embedding import warm_image_model

log = logging.getLogger("app.jobs.ai_ingest_worker")

_last_skip_warn: float = 0.0


async def _slot() -> None:
    global _last_skip_warn
    while True:
        await asyncio.sleep(0.28)
        if not settings.fashn_configured or not settings.yc_s3_configured:
            now = time.monotonic()
            if now - _last_skip_warn >= 90:
                _last_skip_warn = now
                log.warning(
                    "ai_ingest: queue paused — FASHN_API_KEY and YC_S3 keys required. "
                    "fashn_configured=%s yc_s3_configured=%s",
                    settings.fashn_configured,
                    settings.yc_s3_configured,
                )
            await asyncio.sleep(2.5)
            continue
        try:
            await asyncio.to_thread(try_process_one_ingest_job, settings)
        except Exception:
            log.exception("ai_ingest slot error")


async def _outlet_slot() -> None:
    """Кадры аутлета: телефон создаёт задачу через API, Fashn вызывается здесь."""
    while True:
        try:
            did = await asyncio.to_thread(try_process_one_outlet_photo_job)
        except ProgrammingError:
            log.warning("outlet photo: нет таблицы очереди — alembic upgrade head")
            await asyncio.sleep(60)
            continue
        except Exception:
            log.exception("outlet photo: ошибка очереди")
            did = False
        await asyncio.sleep(0.4 if did else 1.2)


async def _stale_watch() -> None:
    while True:
        await asyncio.sleep(300)
        db = SessionLocal()
        try:
            await asyncio.to_thread(reset_stale_processing_jobs, db)
        except Exception:
            db.rollback()
            log.exception("ai_ingest stale watch error")
        finally:
            db.close()


async def _embed_loop() -> None:
    """Модель грузится один раз при старте, дальше — векторы черновиков без embedding."""
    while True:
        try:
            await asyncio.to_thread(warm_image_model)
            break
        except Exception:
            log.exception("embed: модель не загрузилась, повтор через 60 с")
            await asyncio.sleep(60)
    while True:
        try:
            had = await asyncio.to_thread(embed_one_draft_photo)
        except Exception:
            await asyncio.sleep(60)
            continue
        await asyncio.sleep(1 if had else 10)


async def main() -> None:
    setup_logging()
    log.info(
        "ai_ingest_worker start: concurrency=%s fashn=%s yc=%s",
        settings.ai_ingest_worker_concurrency,
        settings.fashn_configured,
        settings.yc_s3_configured,
    )

    db = SessionLocal()
    try:
        # Воркер один: всё, что числится в работе, осталось от прошлого запуска.
        reset_stale_processing_jobs(db, older_than_minutes=0)
        reset_running_jobs(db)
    except ProgrammingError:
        db.rollback()
        log.warning("reset_stale_processing_jobs skipped — run alembic upgrade head first")
    finally:
        db.close()

    n = max(1, settings.ai_ingest_worker_concurrency)
    await asyncio.gather(
        *[_slot() for _ in range(n)],
        _outlet_slot(),
        _outlet_slot(),
        _stale_watch(),
        _embed_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
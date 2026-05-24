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
from app.services.ai_ingest_worker import reset_stale_processing_jobs, try_process_one_ingest_job

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
        reset_stale_processing_jobs(db, older_than_minutes=90)
    except ProgrammingError:
        db.rollback()
        log.warning("reset_stale_processing_jobs skipped — run alembic upgrade head first")
    finally:
        db.close()

    n = max(1, settings.ai_ingest_worker_concurrency)
    await asyncio.gather(*[_slot() for _ in range(n)])


if __name__ == "__main__":
    asyncio.run(main())
"""
VTON 1.5 try-on worker entry point.

Usage:
    python -m jobs.try_on_worker

Loads the FASHN VTON 1.5 model once, then continuously pulls pending
try_on_jobs from the DB and runs local GPU inference.

Requires ~8GB VRAM. Single slot — GPU inference is sequential.

Environment:
    VTON_WEIGHTS_DIR   path to downloaded VTON 1.5 weights (default: ./weights)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from sqlalchemy.exc import ProgrammingError

from app.config import settings
from app.database import SessionLocal
from app.logging_config import setup_logging
from app.services.try_on_worker import reset_stale_try_on_jobs, try_process_one_try_on_job

log = logging.getLogger("app.jobs.try_on_worker")


def _load_pipeline() -> object:
    from fashn_vton import TryOnPipeline  # type: ignore[import]

    weights_dir = os.environ.get("VTON_WEIGHTS_DIR", "./weights")
    log.info("try_on_worker: загружаем VTON 1.5 weights_dir=%s", weights_dir)
    t0 = time.monotonic()
    pipeline = TryOnPipeline(weights_dir=weights_dir)
    log.info("try_on_worker: модель загружена за %.1fs", time.monotonic() - t0)
    return pipeline


async def _slot(pipeline: object) -> None:
    while True:
        await asyncio.sleep(0.5)
        try:
            await asyncio.to_thread(try_process_one_try_on_job, settings, pipeline)
        except Exception:
            log.exception("try_on_worker slot error")


async def main() -> None:
    setup_logging()
    log.info("try_on_worker start: tmp_dir=%s", settings.try_on_tmp_dir)

    db = SessionLocal()
    try:
        reset_stale_try_on_jobs(db, older_than_minutes=30)
    except ProgrammingError:
        db.rollback()
        log.warning("reset_stale_try_on_jobs пропущен — запусти alembic upgrade head")
    finally:
        db.close()

    pipeline = _load_pipeline()
    await _slot(pipeline)


if __name__ == "__main__":
    asyncio.run(main())
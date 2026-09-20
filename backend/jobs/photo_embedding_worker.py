"""
Воркер: векторизация активных фото без embedding.

Usage:
    python -m jobs.photo_embedding_worker

Требует requirements-embeddings.txt (fastembed + onnxruntime). На маленьком VPS
(2 GB RAM) лучше запускать на отдельной машине или после апгрейда RAM.
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy.exc import ProgrammingError

from app.database import SessionLocal
from app.logging_config import setup_logging
from app.services.photo_embedding import try_embed_one_photo

log = logging.getLogger("app.jobs.photo_embedding_worker")

_last_skip_warn: float = 0.0


async def _loop() -> None:
    global _last_skip_warn
    while True:
        await asyncio.sleep(0.5)
        try:
            from fastembed import ImageEmbedding  # noqa: F401
        except ImportError:
            now = time.monotonic()
            if now - _last_skip_warn >= 120:
                _last_skip_warn = now
                log.warning(
                    "photo_embedding: fastembed не установлен — "
                    "pip install -r requirements-embeddings.txt"
                )
            await asyncio.sleep(5.0)
            continue

        db = SessionLocal()
        try:
            had = try_embed_one_photo(db)
        except ProgrammingError:
            db.rollback()
            log.warning("photo_embedding: нет таблиц — выполните alembic upgrade head")
            had = False
        except Exception:
            db.rollback()
            log.exception("photo_embedding worker error")
            had = True
        finally:
            db.close()

        await asyncio.sleep(0.2 if had else 2.0)


async def main() -> None:
    setup_logging()
    log.info("photo_embedding_worker start")
    await _loop()


if __name__ == "__main__":
    asyncio.run(main())

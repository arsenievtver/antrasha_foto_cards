"""
Демо-теги для разработки (фото только из Yandex Object Storage — см. синхронизацию бакетов).

Запуск из каталога backend:
  PYTHONPATH=. python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Tag


def seed(db: Session) -> None:
    if db.execute(select(Tag).limit(1)).scalar_one_or_none():
        print("База уже содержит теги — пропуск seed.")
        return

    tag_specs = [
        ("minimal", "style"),
        ("classic", "style"),
        ("sport", "style"),
        ("black", "color"),
        ("white", "color"),
        ("oversize", "fit"),
        ("slim", "fit"),
    ]
    for name, t in tag_specs:
        db.add(Tag(name=name, type=t))

    db.commit()
    print(f"Seed OK: добавлено {len(tag_specs)} тегов (без фото).")


if __name__ == "__main__":
    s = SessionLocal()
    try:
        seed(s)
    finally:
        s.close()

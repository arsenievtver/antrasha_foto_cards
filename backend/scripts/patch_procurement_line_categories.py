#!/usr/bin/env python3
"""Проставить category_id строкам заказов после import_procurement_merged (если были warn)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

if __name__ == "__main__" and not __package__:
    _root = Path(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from sqlalchemy import select

from app.database import SessionLocal
from app.models.brand_order import BrandOrderCategoryLine
from app.models.category import Category

_NO_CATEGORY = "без разбивки"


def load_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


def build_maps(db, recovery_categories: list[dict]):
    live_name: dict[tuple[str, str], uuid.UUID] = {}
    by_ms: dict[str, uuid.UUID] = {}
    for c in db.scalars(select(Category)).all():
        live_name[(c.name.strip().lower(), c.gender)] = c.id
        if c.moy_sklad_id:
            by_ms[str(c.moy_sklad_id)] = c.id
    rec_by_id = {c["id"]: c for c in recovery_categories}
    return live_name, rec_by_id, by_ms


def resolve_line(
    line: dict,
    live_name: dict[tuple[str, str], uuid.UUID],
    rec_by_id: dict[str, dict],
    by_ms: dict[str, uuid.UUID],
) -> uuid.UUID | None:
    name = (line.get("category_name") or "").strip().lower()
    if name == _NO_CATEGORY:
        return None
    gender = line.get("category_gender") or line.get("gender")
    if name and gender:
        cid = live_name.get((name, gender))
        if cid:
            return cid
    rid = line.get("category_id")
    if rid and rid in rec_by_id:
        rec = rec_by_id[rid]
        ms = rec.get("moy_sklad_id")
        if ms and ms in by_ms:
            return by_ms[ms]
        return live_name.get((rec["name"].strip().lower(), rec["gender"]))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "dir",
        type=Path,
        help="каталог merged (orders.json + categories.json)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    d = args.dir
    orders_path = d / "orders.json"
    cats_path = d / "categories.json"
    if not orders_path.is_file() or not cats_path.is_file():
        print(f"need {orders_path} and {cats_path}", file=sys.stderr)
        return 1

    orders = load_json(orders_path)
    recovery_cats = load_json(cats_path)

    db = SessionLocal()
    try:
        live_name, rec_by_id, by_ms = build_maps(db, recovery_cats)
        patched = 0
        skipped = 0
        missing_row = 0
        for order in orders:
            for ln in order.get("lines") or []:
                cid = resolve_line(ln, live_name, rec_by_id, by_ms)
                if cid is None:
                    continue
                lid = uuid.UUID(ln["id"])
                row = db.get(BrandOrderCategoryLine, lid)
                if not row:
                    missing_row += 1
                    continue
                if row.category_id == cid:
                    skipped += 1
                    continue
                if row.category_id is not None and row.category_id != cid:
                    skipped += 1
                    continue
                patched += 1
                if not args.dry_run:
                    row.category_id = cid
        if args.dry_run:
            db.rollback()
            print(f"[dry-run] would patch {patched} lines (skip {skipped}, no row {missing_row})")
        else:
            db.commit()
            print(f"[ok] patched {patched} lines (skip {skipped}, no row {missing_row})")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

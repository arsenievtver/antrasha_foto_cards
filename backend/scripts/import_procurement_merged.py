#!/usr/bin/env python3
"""Import merged procurement JSON (preserves UUIDs). Run inside backend container."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models.brand import Brand
from app.models.brand_order import BrandOrder, BrandOrderCategoryLine
from app.models.category import Category
from app.models.fx_rate import FxRate
from app.models.payment import Payment
from app.models.season import Season
from app.models.shipment import Shipment


def parse_date(v: str | None) -> date | None:
    if not v:
        return None
    return date.fromisoformat(str(v)[:10])


def parse_dt(v: str | None) -> datetime | None:
    if not v:
        return None
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def dec(v) -> Decimal | None:
    if v is None or v == "":
        return None
    return Decimal(str(v))


def load(path: Path, name: str) -> list[dict]:
    p = path / name
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("items", [])


def build_category_map(
    db, recovery_categories: list[dict]
) -> tuple[dict[tuple[str, str], uuid.UUID], dict[str, dict]]:
    live: dict[tuple[str, str], uuid.UUID] = {}
    for c in db.scalars(select(Category)).all():
        live[(c.name.strip().lower(), c.gender)] = c.id
    rec_by_id = {c["id"]: c for c in recovery_categories}
    return live, rec_by_id


def resolve_category_id(
    live: dict[tuple[str, str], uuid.UUID],
    rec_by_id: dict[str, dict],
    line: dict,
) -> uuid.UUID | None:
    name = (line.get("category_name") or "").strip().lower()
    gender = line.get("category_gender") or line.get("gender")
    if name and gender:
        cid = live.get((name, gender))
        if cid:
            return cid
    rid = line.get("category_id")
    if rid and rid in rec_by_id:
        rec = rec_by_id[rid]
        return live.get((rec["name"].strip().lower(), rec["gender"]))
    return None


def import_seasons(db, items: list[dict], dry_run: bool) -> int:
    n = 0
    for raw in items:
        sid = uuid.UUID(raw["id"])
        if db.get(Season, sid):
            continue
        n += 1
        if dry_run:
            continue
        vis = raw.get("visibility")
        if vis:
            db.execute(
                update(Season).where(Season.visibility == vis).values(visibility=None)
            )
        if raw.get("is_order_plan"):
            db.execute(
                update(Season).where(Season.is_order_plan.is_(True)).values(is_order_plan=False)
            )
        db.add(
            Season(
                id=sid,
                name=raw["name"],
                code=raw["code"],
                is_active=bool(raw.get("is_active", True)),
                is_primary=bool(raw.get("is_primary", False)),
                is_order_plan=bool(raw.get("is_order_plan", False)),
                visibility=vis,
                sort_order=int(raw.get("sort_order") or 0),
                created_at=parse_dt(raw.get("created_at"))
                or datetime.now(timezone.utc),
            )
        )
    db.flush()
    return n


def import_brands(db, items: list[dict], dry_run: bool) -> int:
    n = 0
    for raw in items:
        bid = uuid.UUID(raw["id"])
        if db.get(Brand, bid):
            continue
        n += 1
        if dry_run:
            continue
        db.add(
            Brand(
                id=bid,
                name=raw["name"],
                created_at=parse_dt(raw.get("created_at"))
                or datetime.now(timezone.utc),
            )
        )
    db.flush()
    return n


def import_fx(db, items: list[dict], dry_run: bool) -> int:
    n = 0
    for raw in items:
        fid = uuid.UUID(raw["id"])
        if db.get(FxRate, fid):
            continue
        n += 1
        if dry_run:
            continue
        db.add(
            FxRate(
                id=fid,
                valid_from=parse_date(raw["valid_from"]),
                valid_to=parse_date(raw.get("valid_to")),
                eur_rub=dec(raw["eur_rub"]),
                comment=raw.get("comment"),
                created_at=parse_dt(raw.get("created_at"))
                or datetime.now(timezone.utc),
            )
        )
    db.flush()
    return n


def import_orders(
    db,
    items: list[dict],
    live_cat: dict[tuple[str, str], uuid.UUID],
    rec_by_id: dict[str, dict],
    dry_run: bool,
) -> tuple[int, list[str]]:
    n = 0
    warnings: list[str] = []
    for raw in items:
        oid = uuid.UUID(raw["id"])
        if db.get(BrandOrder, oid):
            continue
        n += 1
        if dry_run:
            continue
        order = BrandOrder(
            id=oid,
            season_id=uuid.UUID(raw["season_id"]),
            brand_id=uuid.UUID(raw["brand_id"]),
            gender=raw.get("gender"),
            ordered_on=parse_date(raw.get("ordered_on")),
            amount_eur=dec(raw.get("amount_eur")) or Decimal("0"),
            eur_rub_rate=dec(raw.get("eur_rub_rate")),
            has_prepayment=bool(raw.get("has_prepayment")),
            prepayment_amount_eur=dec(raw.get("prepayment_amount_eur")),
            prepayment_due_on=parse_date(raw.get("prepayment_due_on")),
            comment=raw.get("comment"),
            created_at=parse_dt(raw.get("created_at")) or datetime.now(timezone.utc),
            updated_at=parse_dt(raw.get("updated_at")) or datetime.now(timezone.utc),
        )
        db.add(order)
        db.flush()
        for ln in raw.get("lines") or []:
            cid = resolve_category_id(live_cat, rec_by_id, ln)
            if cid is None:
                warnings.append(
                    f"order {oid}: category not mapped: {ln.get('category_name')}"
                )
            gender = ln.get("category_gender") or ln.get("gender") or raw.get("gender") or "men"
            db.add(
                BrandOrderCategoryLine(
                    id=uuid.UUID(ln["id"]),
                    order_id=oid,
                    category_id=cid,
                    gender=gender,
                    amount_eur=dec(ln.get("amount_eur")) or Decimal("0"),
                    comment=ln.get("comment"),
                    created_at=parse_dt(ln.get("created_at"))
                    or datetime.now(timezone.utc),
                )
            )
    db.flush()
    return n, warnings


def import_payments(db, items: list[dict], dry_run: bool) -> int:
    n = 0
    for raw in items:
        pid = uuid.UUID(raw["id"])
        if db.get(Payment, pid):
            continue
        n += 1
        if dry_run:
            continue
        oid = raw.get("order_id")
        db.add(
            Payment(
                id=pid,
                order_id=uuid.UUID(oid) if oid else None,
                season_id=uuid.UUID(raw["season_id"]),
                brand_id=uuid.UUID(raw["brand_id"]),
                paid_on=parse_date(raw["paid_on"]),
                kind=raw.get("kind") or "main",
                amount_eur=dec(raw["amount_eur"]) or Decimal("0"),
                eur_rub_rate=dec(raw.get("eur_rub_rate")),
                amount_rub=dec(raw.get("amount_rub")),
                comment=raw.get("comment"),
                created_at=parse_dt(raw.get("created_at"))
                or datetime.now(timezone.utc),
            )
        )
    db.flush()
    return n


def import_shipments(db, items: list[dict], dry_run: bool) -> int:
    n = 0
    for raw in items:
        sid = uuid.UUID(raw["id"])
        if db.get(Shipment, sid):
            continue
        n += 1
        if dry_run:
            continue
        oid = raw.get("order_id")
        db.add(
            Shipment(
                id=sid,
                order_id=uuid.UUID(oid) if oid else None,
                season_id=uuid.UUID(raw["season_id"]),
                brand_id=uuid.UUID(raw["brand_id"]),
                shipped_on=parse_date(raw["shipped_on"]),
                amount_eur=dec(raw["amount_eur"]) or Decimal("0"),
                weight_kg=dec(raw.get("weight_kg")),
                eur_rub_rate=dec(raw.get("eur_rub_rate")),
                amount_rub=dec(raw.get("amount_rub")),
                comment=raw.get("comment"),
                logistics_amount_rub=dec(raw.get("logistics_amount_rub")),
                logistics_paid_on=parse_date(raw.get("logistics_paid_on")),
                is_delivered=bool(raw.get("is_delivered", True)),
                created_at=parse_dt(raw.get("created_at"))
                or datetime.now(timezone.utc),
            )
        )
    db.flush()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path, help="merged JSON directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    d: Path = args.dir
    if not d.is_dir():
        print(f"not a directory: {d}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        live_cat, rec_by_id = build_category_map(db, load(d, "categories.json"))
        stats = {
            "seasons": import_seasons(db, load(d, "seasons.json"), args.dry_run),
            "brands": import_brands(db, load(d, "brands.json"), args.dry_run),
            "fx_rates": import_fx(db, load(d, "fx_rates.json"), args.dry_run),
        }
        on, warns = import_orders(
            db, load(d, "orders.json"), live_cat, rec_by_id, args.dry_run
        )
        stats["orders"] = on
        stats["payments"] = import_payments(db, load(d, "payments.json"), args.dry_run)
        stats["shipments"] = import_shipments(db, load(d, "shipments.json"), args.dry_run)
        if args.dry_run:
            db.rollback()
            print("[dry-run]", stats)
        else:
            db.commit()
            print("[ok]", stats)
        for w in warns[:20]:
            print("warn:", w)
        if len(warns) > 20:
            print(f"... +{len(warns) - 20} warnings")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

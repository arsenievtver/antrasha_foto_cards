"""Список клиентов А: снимок из недель, история и кто из сотрудников о ком пишет."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.a_client import AClient, AClientCaretaker, AClientWeek
from app.models.staff_feedback import StaffFeedback
from app.models.weekly_insight_report import WeeklyInsightReport
from app.services.a_client_match import match_client, plan_auto_threads
from app.services.weekly_insight.compute import WATCH_STATUSES

_STATUS_ORDER = {name: i for i, name in enumerate(WATCH_STATUSES)}


def author_key(user_id: uuid.UUID | None, label: str) -> str:
    if user_id:
        return str(user_id)
    return f"label:{(label or '').strip()}"


def _as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_int(value) -> int | None:
    if value is None:
        return None
    return int(value)


def _apply_snapshot(client: AClient, entry: dict, week: date) -> None:
    client.name = (entry.get("name") or client.name or "—")[:300]
    client.phone = (entry.get("phone") or None)
    if client.phone:
        client.phone = str(client.phone)[:32]
    client.status = entry.get("status")
    client.last_visit = _as_date(entry.get("last"))
    client.days_since = _as_int(entry.get("days_since"))
    client.median_gap = _as_float(entry.get("median_gap"))
    client.visits = _as_int(entry.get("visits"))
    client.rev_prev12 = _as_float(entry.get("rev_prev12"))
    client.rev_cur12 = _as_float(entry.get("rev_cur12"))
    client.brands = list(entry.get("brands") or [])
    client.categories = list(entry.get("categories") or [])
    client.sizes = entry.get("sizes") or None
    client.avg_discount_pct = _as_float(entry.get("avg_discount_pct"))
    client.markdown_share_pct = _as_float(entry.get("markdown_share_pct"))
    client.picks = list(entry.get("picks") or [])
    if client.first_week is None or week < client.first_week:
        client.first_week = week
    if client.last_week is None or week >= client.last_week:
        client.last_week = week


def _apply_week(row: AClientWeek, entry: dict, report_id: uuid.UUID, week: date) -> None:
    row.report_id = report_id
    row.week_start = week
    row.status = entry.get("status")
    row.last_visit = _as_date(entry.get("last"))
    row.days_since = _as_int(entry.get("days_since"))
    row.visits = _as_int(entry.get("visits"))
    row.rev_prev12 = _as_float(entry.get("rev_prev12"))
    row.rev_cur12 = _as_float(entry.get("rev_cur12"))


def sync_watchlists(db: Session) -> dict:
    """Пересобрать клиентов и недели из готовых отчётов. Повторный запуск ничего не дублирует."""
    reports = list(
        db.scalars(
            select(WeeklyInsightReport)
            .where(WeeklyInsightReport.status == "done", WeeklyInsightReport.watchlist.is_not(None))
            .order_by(WeeklyInsightReport.week_start, WeeklyInsightReport.finished_at)
        ).all()
    )
    latest_by_week: dict[date, WeeklyInsightReport] = {}
    for report in reports:
        latest_by_week[report.week_start] = report
    if not latest_by_week:
        return {"reports": 0, "clients": 0, "active": 0}

    latest_report = max(latest_by_week.values(), key=lambda r: (r.week_start, r.finished_at or r.started_at))
    latest_ids: set[str] = set()
    known: dict[str, AClient] = {
        row.counterparty_id: row for row in db.scalars(select(AClient)).all()
    }
    # Снимок на карточке — последнее появление. Идём по неделям от старых к новым.
    for week in sorted(latest_by_week):
        report = latest_by_week[week]
        for entry in report.watchlist or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            cid = str(entry["id"])
            client = known.get(cid)
            if client is None:
                client = AClient(counterparty_id=cid, name=(entry.get("name") or "—")[:300])
                db.add(client)
                db.flush()
                known[cid] = client
            if client.last_week is None or week >= client.last_week:
                _apply_snapshot(client, entry, week)
            else:
                if client.first_week is None or week < client.first_week:
                    client.first_week = week
            week_row = db.scalar(
                select(AClientWeek).where(AClientWeek.client_id == client.id, AClientWeek.week_start == week)
            )
            if week_row is None:
                week_row = AClientWeek(client_id=client.id, week_start=week)
                db.add(week_row)
            _apply_week(week_row, entry, report.id, week)
            if report.id == latest_report.id:
                latest_ids.add(cid)
    for client in known.values():
        client.active = client.counterparty_id in latest_ids
    db.flush()
    return {"reports": len(latest_by_week), "clients": len(known), "active": len(latest_ids)}


def _catalog(db: Session) -> list[dict]:
    return [{"id": str(row.id), "name": row.name} for row in db.scalars(select(AClient)).all()]


def assign_comments(db: Session) -> dict:
    """Склеить обрывки одной мысли и проставить клиента там, где привязку ещё не фиксировали руками."""
    catalog = _catalog(db)
    rows = list(db.scalars(select(StaffFeedback).order_by(StaffFeedback.created_at)).all())
    payload = [
        {
            "id": str(row.id),
            "author_key": author_key(row.author_user_id, row.author_label),
            "created_at": row.created_at,
            "text": row.text,
            "thread_id": str(row.thread_id) if row.thread_id else None,
            "thread_locked": bool(row.thread_locked),
        }
        for row in rows
    ]
    groups = plan_auto_threads(payload, catalog)
    by_id = {str(row.id): row for row in rows}
    merged = 0
    for group in groups:
        thread = uuid.uuid4()
        for item_id in group:
            by_id[item_id].thread_id = thread
            merged += 1

    threads: dict[str, list[StaffFeedback]] = {}
    for row in rows:
        key = str(row.thread_id) if row.thread_id else str(row.id)
        threads.setdefault(key, []).append(row)

    linked = 0
    for group in threads.values():
        group.sort(key=lambda row: row.created_at)
        hit = match_client("\n".join(row.text for row in group), catalog)
        if hit is None:
            hits = {match_client(row.text, catalog) for row in group}
            hits.discard(None)
            hit = hits.pop() if len(hits) == 1 else None
        client_uuid = uuid.UUID(hit) if hit else None
        for row in group:
            if row.client_binding in ("manual", "none"):
                continue
            row.client_id = client_uuid
            row.client_binding = "auto" if client_uuid else None
            if client_uuid:
                linked += 1
    caretakers = rebuild_caretakers(db)
    db.flush()
    return {"merged_messages": merged, "linked_messages": linked, "caretakers": caretakers}


def rebuild_caretakers(db: Session) -> int:
    """Автор комментария о клиенте становится его сотрудником. Ручные и снятые не затираются."""
    comments = list(
        db.scalars(
            select(StaffFeedback).where(
                StaffFeedback.client_id.is_not(None),
                StaffFeedback.client_binding.is_distinct_from("none"),
            )
        ).all()
    )
    wanted: dict[uuid.UUID, dict[str, tuple]] = {}
    for row in comments:
        if row.client_id is None:
            continue
        key = author_key(row.author_user_id, row.author_label)
        wanted.setdefault(row.client_id, {})[key] = (row.author_user_id, row.author_label)
    existing = {(row.client_id, row.author_key): row for row in db.scalars(select(AClientCaretaker)).all()}
    wanted_keys: set[tuple[uuid.UUID, str]] = set()
    for client_id, authors in wanted.items():
        for key, (user_id, label) in authors.items():
            wanted_keys.add((client_id, key))
            row = existing.get((client_id, key))
            if row is None:
                db.add(
                    AClientCaretaker(
                        client_id=client_id,
                        author_user_id=user_id,
                        author_label=label,
                        author_key=key,
                        source="comment",
                        active=True,
                        dismissed=False,
                    )
                )
            elif row.dismissed:
                continue
            else:
                row.active = True
                row.author_label = label
                row.author_user_id = user_id or row.author_user_id
                if row.source != "manual":
                    row.source = "comment"
    for (client_id, key), row in existing.items():
        if row.source == "manual" or row.dismissed:
            continue
        if (client_id, key) not in wanted_keys:
            row.active = False
    db.flush()
    return len(wanted_keys)


def refresh_from_reports(db: Session) -> dict:
    stats = sync_watchlists(db)
    stats.update(assign_comments(db))
    return stats


def _caretaker_dict(row: AClientCaretaker) -> dict:
    return {
        "id": str(row.id),
        "author_user_id": str(row.author_user_id) if row.author_user_id else None,
        "author_label": row.author_label,
        "source": row.source,
        "active": row.active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _week_dict(row: AClientWeek) -> dict:
    return {
        "week_start": row.week_start.isoformat(),
        "status": row.status,
        "last_visit": row.last_visit.isoformat() if row.last_visit else None,
        "days_since": row.days_since,
        "visits": row.visits,
        "rev_prev12": row.rev_prev12,
        "rev_cur12": row.rev_cur12,
    }


def _progress(weeks: list[AClientWeek], active: bool) -> dict:
    ordered = sorted(weeks, key=lambda row: row.week_start)
    first = ordered[0] if ordered else None
    last = ordered[-1] if ordered else None
    return {
        "weeks_on_list": len(ordered),
        "on_list_now": active,
        "first_week": first.week_start.isoformat() if first else None,
        "last_week": last.week_start.isoformat() if last else None,
        "rev_cur12_first": first.rev_cur12 if first else None,
        "rev_cur12_last": last.rev_cur12 if last else None,
        "days_since_first": first.days_since if first else None,
        "days_since_last": last.days_since if last else None,
        "status_first": first.status if first else None,
        "status_last": last.status if last else None,
    }


def list_clients(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    active: bool | None = None,
    caretaker: str | None = None,
    without_caretaker: bool = False,
) -> list[dict]:
    clients = list(db.scalars(select(AClient)).all())
    week_rows = list(db.scalars(select(AClientWeek)).all())
    weeks_by: dict[uuid.UUID, list[AClientWeek]] = {}
    for row in week_rows:
        weeks_by.setdefault(row.client_id, []).append(row)
    caretaker_rows = list(db.scalars(select(AClientCaretaker).where(AClientCaretaker.active.is_(True))).all())
    care_by: dict[uuid.UUID, list[AClientCaretaker]] = {}
    for row in caretaker_rows:
        care_by.setdefault(row.client_id, []).append(row)
    comments = list(
        db.scalars(
            select(StaffFeedback)
            .where(StaffFeedback.client_id.is_not(None))
            .order_by(StaffFeedback.created_at.desc())
        ).all()
    )
    last_by: dict[uuid.UUID, StaffFeedback] = {}
    count_by: dict[uuid.UUID, int] = {}
    for row in comments:
        if row.client_id is None or row.client_binding == "none":
            continue
        count_by[row.client_id] = count_by.get(row.client_id, 0) + 1
        last_by.setdefault(row.client_id, row)

    needle = (q or "").strip().lower()
    out = []
    for client in clients:
        if active is not None and client.active is not active:
            continue
        if status and client.status != status:
            continue
        if needle and needle not in client.name.lower() and needle not in (client.phone or ""):
            continue
        people = care_by.get(client.id, [])
        if without_caretaker and people:
            continue
        if caretaker:
            keys = {row.author_key for row in people} | {row.author_label for row in people}
            if caretaker not in keys:
                continue
        last = last_by.get(client.id)
        progress = _progress(weeks_by.get(client.id, []), client.active)
        out.append(
            {
                "id": str(client.id),
                "name": client.name,
                "phone": client.phone,
                "status": client.status,
                "active": client.active,
                "last_visit": client.last_visit.isoformat() if client.last_visit else None,
                "days_since": client.days_since,
                "median_gap": client.median_gap,
                "visits": client.visits,
                "rev_prev12": client.rev_prev12,
                "rev_cur12": client.rev_cur12,
                "brands": client.brands or [],
                "categories": client.categories or [],
                "sizes": client.sizes,
                "avg_discount_pct": client.avg_discount_pct,
                "markdown_share_pct": client.markdown_share_pct,
                "picks": client.picks or [],
                "first_week": client.first_week.isoformat() if client.first_week else None,
                "last_week": client.last_week.isoformat() if client.last_week else None,
                "weeks_on_list": progress["weeks_on_list"],
                "caretakers": [_caretaker_dict(row) for row in people],
                "comment_count": count_by.get(client.id, 0),
                "last_comment_at": last.created_at.isoformat() if last and last.created_at else None,
                "last_comment_text": (last.text[:180] if last else None),
                "last_comment_author": last.author_label if last else None,
            }
        )
    out.sort(
        key=lambda row: (
            not row["active"],
            _STATUS_ORDER.get(row["status"] or "", 9),
            -(row["rev_prev12"] or 0),
            row["name"],
        )
    )
    return out


def _comment_groups(rows: list[StaffFeedback]) -> list[dict]:
    ordered = sorted(rows, key=lambda row: row.created_at)
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for row in ordered:
        if row.client_binding == "none":
            continue
        key = str(row.thread_id) if row.thread_id else str(row.id)
        group = index.get(key)
        if group is None:
            group = {
                "thread_id": str(row.thread_id) if row.thread_id else None,
                "author_label": row.author_label,
                "author_user_id": str(row.author_user_id) if row.author_user_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "binding": row.client_binding,
                "parts": [],
            }
            index[key] = group
            groups.append(group)
        group["parts"].append(
            {
                "id": str(row.id),
                "text": row.text,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return groups


def get_client(db: Session, client_id: uuid.UUID) -> dict | None:
    client = db.get(AClient, client_id)
    if client is None:
        return None
    weeks = list(
        db.scalars(
            select(AClientWeek).where(AClientWeek.client_id == client.id).order_by(AClientWeek.week_start)
        ).all()
    )
    people = list(
        db.scalars(
            select(AClientCaretaker)
            .where(AClientCaretaker.client_id == client.id, AClientCaretaker.active.is_(True))
            .order_by(AClientCaretaker.created_at)
        ).all()
    )
    comments = list(
        db.scalars(select(StaffFeedback).where(StaffFeedback.client_id == client.id)).all()
    )
    return {
        "id": str(client.id),
        "counterparty_id": client.counterparty_id,
        "name": client.name,
        "phone": client.phone,
        "status": client.status,
        "active": client.active,
        "last_visit": client.last_visit.isoformat() if client.last_visit else None,
        "days_since": client.days_since,
        "median_gap": client.median_gap,
        "visits": client.visits,
        "rev_prev12": client.rev_prev12,
        "rev_cur12": client.rev_cur12,
        "brands": client.brands or [],
        "categories": client.categories or [],
        "sizes": client.sizes,
        "avg_discount_pct": client.avg_discount_pct,
        "markdown_share_pct": client.markdown_share_pct,
        "picks": client.picks or [],
        "first_week": client.first_week.isoformat() if client.first_week else None,
        "last_week": client.last_week.isoformat() if client.last_week else None,
        "caretakers": [_caretaker_dict(row) for row in people],
        "weeks": [_week_dict(row) for row in weeks],
        "progress": _progress(weeks, client.active),
        "comments": _comment_groups(comments),
    }


def set_feedback_client(db: Session, feedback_id: uuid.UUID, client_id: uuid.UUID | None) -> StaffFeedback:
    row = db.get(StaffFeedback, feedback_id)
    if row is None:
        raise LookupError("Сообщение не найдено")
    if client_id is not None and db.get(AClient, client_id) is None:
        raise LookupError("Клиент не найден")
    targets = [row]
    if row.thread_id:
        targets = list(db.scalars(select(StaffFeedback).where(StaffFeedback.thread_id == row.thread_id)).all())
    for target in targets:
        target.client_id = client_id
        target.client_binding = "manual" if client_id else "none"
    rebuild_caretakers(db)
    db.flush()
    return row


def merge_feedback(db: Session, ids: list[uuid.UUID]) -> uuid.UUID:
    rows = list(db.scalars(select(StaffFeedback).where(StaffFeedback.id.in_(ids))).all())
    if len(rows) != len(set(ids)) or len(rows) < 2:
        raise ValueError("Нужны существующие сообщения")
    authors = {(row.author_user_id, row.author_label) for row in rows}
    if len(authors) != 1:
        raise ValueError("Объединять можно только сообщения одного сотрудника")
    chosen = {row.id for row in rows}
    old_threads = {row.thread_id for row in rows if row.thread_id}
    thread = uuid.uuid4()
    if len(old_threads) == 1:
        only = next(iter(old_threads))
        members = list(db.scalars(select(StaffFeedback).where(StaffFeedback.thread_id == only)).all())
        if {member.id for member in members} <= chosen:
            thread = only
    for row in rows:
        row.thread_id = thread
        row.thread_locked = True
    for old in old_threads:
        if old == thread:
            continue
        left = list(
            db.scalars(
                select(StaffFeedback).where(
                    StaffFeedback.thread_id == old,
                    StaffFeedback.id.not_in(chosen),
                )
            ).all()
        )
        if len(left) < 2:
            for item in left:
                item.thread_id = None
                item.thread_locked = True
    db.flush()
    return thread


def split_thread(db: Session, thread_id: uuid.UUID) -> int:
    rows = list(db.scalars(select(StaffFeedback).where(StaffFeedback.thread_id == thread_id)).all())
    if not rows:
        raise LookupError("Такой склейки нет")
    for row in rows:
        row.thread_id = None
        row.thread_locked = True
    db.flush()
    return len(rows)


def add_caretaker(
    db: Session,
    client_id: uuid.UUID,
    *,
    author_user_id: uuid.UUID | None,
    author_label: str,
) -> AClientCaretaker:
    if db.get(AClient, client_id) is None:
        raise LookupError("Клиент не найден")
    label = author_label.strip()
    if not label:
        raise ValueError("Нужно имя сотрудника")
    key = author_key(author_user_id, label)
    row = db.scalar(
        select(AClientCaretaker).where(
            AClientCaretaker.client_id == client_id,
            AClientCaretaker.author_key == key,
        )
    )
    if row is None:
        row = AClientCaretaker(
            client_id=client_id,
            author_user_id=author_user_id,
            author_label=label,
            author_key=key,
            source="manual",
            active=True,
            dismissed=False,
        )
        db.add(row)
    else:
        row.author_label = label
        row.author_user_id = author_user_id or row.author_user_id
        row.source = "manual"
        row.active = True
        row.dismissed = False
    db.flush()
    return row


def dismiss_caretaker(db: Session, client_id: uuid.UUID, caretaker_id: uuid.UUID) -> None:
    row = db.get(AClientCaretaker, caretaker_id)
    if row is None or row.client_id != client_id:
        raise LookupError("Привязка не найдена")
    row.active = False
    row.dismissed = True
    db.flush()

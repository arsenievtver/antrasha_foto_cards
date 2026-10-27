"""Недельные отчёты по МойСклад через MCP закупок. Только чтение, только ключ суперпользователя."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mcp_procurement.registry import (
    ToolArgumentError,
    ToolPermissionError,
    check_limit,
    tool,
)
from app.models.mcp_api_key import OWNER_SUPERUSER
from app.models.weekly_insight_report import WeeklyInsightReport
from app.services.mcp_keys import McpActor
from app.services.weekly_insight.runner import report_dict
from app.services.weekly_insight.summary import compact_metrics

MAX_REPORTS = 52
DETAILS = ("summary", "compact", "full")


def _require_superuser_key(actor: McpActor) -> None:
    if actor.owner_role != OWNER_SUPERUSER:
        raise ToolPermissionError("Недельные отчёты доступны только по ключу суперпользователя.")


@tool(
    "list_weekly_reports",
    "Недельные отчёты по МойСклад, новые сначала, только ключ суперпользователя: неделя (понедельник), "
    "статус running/done/error, кто запустил (schedule — по расписанию в понедельник утром, manual — кнопкой в админке), "
    "размер списка клиентов на контроле. Только чтение.",
    {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": f"Сколько отчётов, от 1 до {MAX_REPORTS}. По умолчанию 10."},
        },
    },
)
def list_weekly_reports_tool(db: Session, actor: McpActor, limit: int | None = None) -> list[dict]:
    _require_superuser_key(actor)
    rows = db.scalars(
        select(WeeklyInsightReport)
        .order_by(WeeklyInsightReport.started_at.desc())
        .limit(check_limit(limit or 10, MAX_REPORTS))
    ).all()
    return [report_dict(r) for r in rows]


@tool(
    "get_weekly_report",
    "Недельный отчёт по МойСклад, только ключ суперпользователя. Без report_id — последний готовый. "
    "detail: summary — только текст (разделы «В общем», «За неделю», «Динамика», «Предложения»); "
    "compact (по умолчанию) — текст и метрики с верхом списков; full — все метрики. "
    "Метрики: week (неделя пн–вс к прошлой неделе и к году назад, новые покупатели, клиенты A, вернувшиеся из прошлого списка), "
    "dynamics (13 недель), overall (12 мес к прошлым 12, закупка против себестоимости, склад, запас в месяцах), "
    "clients (сегменты A/B/C и статусы A), assortment (сезоны, категории, бренды, размерная сетка, мёртвый сток, кандидаты на дозаказ). "
    "Суммы в рублях. Список клиентов на контроле с ФИО и телефонами — только при include_watchlist=true. Только чтение.",
    {
        "type": "object",
        "properties": {
            "report_id": {"type": "string", "format": "uuid", "description": "id из list_weekly_reports"},
            "detail": {"type": "string", "enum": list(DETAILS), "description": "Объём ответа, по умолчанию compact"},
            "include_watchlist": {"type": "boolean", "description": "Добавить клиентов A на контроле с подборками"},
            "watchlist_limit": {"type": "integer", "description": "Сколько клиентов из списка, по умолчанию 30"},
        },
    },
)
def get_weekly_report_tool(
    db: Session,
    actor: McpActor,
    report_id: str | None = None,
    detail: str | None = None,
    include_watchlist: bool | None = None,
    watchlist_limit: int | None = None,
) -> dict:
    _require_superuser_key(actor)
    detail = detail or "compact"
    if detail not in DETAILS:
        raise ToolArgumentError(f"detail: одно из {', '.join(DETAILS)}")
    if report_id:
        try:
            row = db.get(WeeklyInsightReport, uuid.UUID(report_id))
        except ValueError as exc:
            raise ToolArgumentError("report_id должен быть UUID") from exc
    else:
        row = db.scalars(
            select(WeeklyInsightReport)
            .where(WeeklyInsightReport.status == "done")
            .order_by(WeeklyInsightReport.started_at.desc())
            .limit(1)
        ).first()
    if row is None:
        raise ToolArgumentError("Отчёт не найден")
    out = report_dict(row)
    out["summary_md"] = row.summary_md
    if detail != "summary" and row.metrics:
        out["metrics"] = row.metrics if detail == "full" else compact_metrics(row.metrics)
    if include_watchlist:
        out["watchlist"] = (row.watchlist or [])[: check_limit(watchlist_limit or 30, 200)]
    return out

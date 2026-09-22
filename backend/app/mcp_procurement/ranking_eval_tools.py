"""Чтение истории оценки ранжирования через тот же MCP, что и закупки."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.mcp_procurement.registry import ToolArgumentError, check_limit, tool
from app.services.mcp_keys import McpActor
from app.services.ranking_eval_inspect import (
    get_ranking_eval_submission,
    list_ranking_eval_submissions,
)

_UUID = {"type": "string", "format": "uuid"}


def _uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


@tool(
    "list_ranking_eval_submissions",
    "Список отправок «Оценить подборку»: кто, набор, τ, ρ, top-3 и снимок настроек ленты "
    "на момент отправки. Только чтение. Идентификатор для разбора — get_ranking_eval_submission.",
    {
        "type": "object",
        "properties": {
            "gender": {
                "type": "string",
                "enum": ["male", "female"],
                "description": "Фильтр по полу набора",
            },
            "benchmark_id": {**_UUID, "description": "Фильтр по id набора"},
            "limit": {
                "type": "integer",
                "description": "Сколько последних отправок, от 1 до 200. По умолчанию 50.",
            },
        },
    },
)
def list_ranking_eval_submissions_tool(
    db: Session,
    actor: McpActor,
    gender: str | None = None,
    benchmark_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    _ = actor
    if gender is not None and gender not in ("male", "female"):
        raise ToolArgumentError("gender должен быть male или female")
    bench = _uuid(benchmark_id, "benchmark_id") if benchmark_id else None
    return list_ranking_eval_submissions(
        db,
        gender=gender,
        benchmark_id=bench,
        limit=check_limit(limit),
    )


@tool(
    "get_ranking_eval_submission",
    "Разбор одной отправки: порядок человека и модели, url фото, снимок настроек и текущие "
    "настройки ленты, разброс эмбеддингов набора, косинус к вектору вкуса, swipe_updates "
    "и число like/dislike по полу. Сырые векторы не возвращаются. "
    "signals: ranking_mode_was_tags, no_taste_vector_for_gender, "
    "benchmark_embeddings_very_close, taste_scores_almost_flat.",
    {
        "type": "object",
        "properties": {
            "submission_id": {**_UUID, "description": "id отправки из list_ranking_eval_submissions"},
        },
        "required": ["submission_id"],
    },
)
def get_ranking_eval_submission_tool(
    db: Session,
    actor: McpActor,
    submission_id: str,
) -> dict:
    _ = actor
    found = get_ranking_eval_submission(db, _uuid(submission_id, "submission_id"))
    if found is None:
        raise ToolArgumentError("Отправка не найдена")
    return found

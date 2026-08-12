"""
Orchestrator: agentic tool-loop по semantic operations.

Свободный вопрос → Claude вызывает наши tools → backend исполняет МойСклад REST
→ tool_result с реальными данными → следующий шаг / финальный ответ.

Пресеты → прямой exec без агента (детерминированно) + короткий writer.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from app.config import Settings
from app.services.warehouse_analytics.catalog import (
    KNOWN_OPERATION_IDS,
    anthropic_tools,
)
from app.services.warehouse_analytics.ms_client import (
    MoySkladAnalyticsClient,
    MoySkladAnalyticsError,
)
from app.services.warehouse_analytics.operations import run_operation

log = logging.getLogger("app.warehouse_analytics.orch")

_TZ = ZoneInfo("Europe/Moscow")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOOL_ROUNDS = 8
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 529})
_MAX_RETRIES = 4
_RETRY_BASE_SEC = 1.5
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_PLACEHOLDER_RE = re.compile(
    r"<<|>>|top_counterparty|step_?\d|placeholder|from_previous|\{\{",
    re.I,
)

PRESET_PLANS: dict[str, list[dict[str, Any]]] = {
    "stock_overview": [
        {"operation": "stock_snapshot", "args": {"store": "antrasha", "mode": "positive", "limit": 15}},
    ],
    "low_stock": [
        {"operation": "stock_snapshot", "args": {"store": "antrasha", "mode": "low", "limit": 20}},
    ],
    "sales_week": [
        {"operation": "revenue_series", "args": {"interval": "day"}},
        {"operation": "dashboard_period", "args": {"period": "week"}},
        {"operation": "profit_top_products", "args": {"limit": 10, "store": "antrasha"}},
    ],
    "sales_month": [
        {"operation": "dashboard_period", "args": {"period": "month"}},
        {"operation": "revenue_series", "args": {"interval": "day"}},
        {"operation": "profit_top_products", "args": {"limit": 15, "store": "antrasha"}},
    ],
    "sales_year_chart": [
        {"operation": "revenue_series", "args": {"interval": "month"}},
    ],
    "margin_leaders": [
        {"operation": "profit_top_products", "args": {"limit": 15, "sort": "sell", "store": "antrasha"}},
        {"operation": "profit_top_products", "args": {"limit": 15, "sort": "profit", "store": "antrasha"}},
    ],
    "open_orders": [
        {"operation": "open_orders", "args": {"limit": 15}},
    ],
    "assortment_search": [
        {"operation": "stock_snapshot", "args": {"store": "antrasha", "mode": "positive", "limit": 5}},
    ],
}


def semantic_configured(settings: Settings) -> bool:
    return bool(
        settings.anthropic_api_key
        and str(settings.anthropic_api_key).strip()
        and settings.moysklad_token
        and str(settings.moysklad_token).strip()
    )


def _proxies(settings: Settings) -> dict[str, str] | None:
    proxy = (
        str(settings.anthropic_https_proxy).strip()
        if settings.anthropic_https_proxy and str(settings.anthropic_https_proxy).strip()
        else None
    )
    return {"http": proxy, "https": proxy} if proxy else None


def _merge_usage(dst: dict[str, int], src: object) -> None:
    if not isinstance(src, dict):
        return
    for key in ("input_tokens", "output_tokens"):
        if key in src and src[key] is not None:
            try:
                dst[key] = dst.get(key, 0) + int(src[key])
            except (TypeError, ValueError):
                pass


def _today() -> datetime.date:
    return datetime.now(_TZ).date()


def _fill_preset_args(operation: str, args: dict[str, Any], *, preset_id: str) -> dict[str, Any]:
    from datetime import date as date_cls

    out = dict(args)
    today = _today()
    if operation == "revenue_series":
        if preset_id == "sales_week":
            out["date_from"] = (today - timedelta(days=6)).isoformat()
            out["date_to"] = today.isoformat()
            out["interval"] = "day"
        elif preset_id == "sales_month":
            out["date_from"] = today.replace(day=1).isoformat()
            out["date_to"] = today.isoformat()
            out["interval"] = "day"
        elif preset_id == "sales_year_chart":
            y, m = today.year, today.month - 11
            while m <= 0:
                m += 12
                y -= 1
            out["date_from"] = date_cls(y, m, 1).isoformat()
            out["date_to"] = today.isoformat()
            out["interval"] = "month"
    if operation == "profit_top_products":
        out.setdefault("date_from", today.replace(day=1).isoformat())
        out.setdefault("date_to", today.isoformat())
        if preset_id == "sales_week":
            out["date_from"] = (today - timedelta(days=6)).isoformat()
            out["date_to"] = today.isoformat()
    return out


def _anthropic_raw(
    settings: Settings,
    *,
    model: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    api_key = str(settings.anthropic_api_key).strip()
    timeout = max(30.0, float(settings.anthropic_http_timeout or 180.0))
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    proxies = _proxies(settings)
    last_err = "unknown"
    for attempt in range(_MAX_RETRIES + 1):
        try:
            res = requests.post(
                ANTHROPIC_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
                proxies=proxies,
            )
        except requests.RequestException as e:
            last_err = str(e)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_SEC * (2**attempt))
                continue
            raise RuntimeError(f"Сеть Anthropic: {e}") from e
        try:
            data = res.json()
        except ValueError:
            data = {"raw": (res.text or "")[:400]}
        if res.status_code < 400:
            return data if isinstance(data, dict) else {"content": [], "stop_reason": "end_turn"}
        detail = data.get("error", data) if isinstance(data, dict) else data
        msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        last_err = f"Anthropic HTTP {res.status_code}: {msg}"
        if res.status_code in _RETRYABLE_HTTP and attempt < _MAX_RETRIES:
            delay = _RETRY_BASE_SEC * (2**attempt)
            ra = res.headers.get("retry-after")
            if ra:
                try:
                    delay = max(delay, float(ra))
                except ValueError:
                    pass
            log.warning("anthropic retry HTTP %s sleep=%.1fs", res.status_code, delay)
            time.sleep(delay)
            continue
        hint = " — Anthropic перегружен, повторите позже." if res.status_code == 529 else ""
        raise RuntimeError(f"{last_err}{hint}")
    raise RuntimeError(last_err)


def _sanitize_tool_input(name: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Отбрасываем выдуманные args; ошибка уходит в tool_result, модель исправляется на следующем шаге."""
    args = dict(raw or {})
    for key, val in list(args.items()):
        if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
            raise ValueError(
                f"Запрещён placeholder в {name}.{key}={val!r}. "
                "Сначала дождись tool_result, затем вызови tool с реальными id/именами из него."
            )
    if name == "customer_purchases":
        cid = str(args.get("counterparty_id") or "").strip()
        cname = str(args.get("counterparty_name") or "").strip()
        if cid and not _UUID_RE.match(cid):
            args.pop("counterparty_id", None)
            cid = ""
        if not cid and not cname:
            raise ValueError(
                "customer_purchases требует counterparty_id (UUID из top_counterparties.best.id / items[].id) "
                "или counterparty_name из вопроса пользователя."
            )
    return args


def _compact_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Ужимаем facts для следующего хода модели (токены)."""
    out = {k: v for k, v in result.items() if k != "cache_hit"}
    # обрезать длинные списки уже сделано в operations; доп. страховка
    for key in ("items", "products", "lines", "top_items", "points", "stock_items"):
        if isinstance(out.get(key), list) and len(out[key]) > 30:
            out[key] = out[key][:30]
            out[f"{key}_truncated"] = True
    return out


def _agent_system() -> str:
    today = _today().isoformat()
    return f"""\
Ты аналитик розничного магазина одежды ANTRASHA (Тверь). Сегодня (Europe/Moscow): {today}.

У тебя есть tools к МойСклад (только чтение). Правила:
1. Сначала вызови нужные tools, потом дай итоговый ответ с цифрами (Markdown, таблицы GFM).
2. Не выдумывай цифры — только из tool results.
3. Когда пользователь говорит «бренд», «марка» или «поставщик» — это поле «Поставщик» (supplier) в карточке товара МойСклад.
   Продажи бренда/сезона: tool brand_sales (как UI Прибыльность). Источник: lines[].brand / by_brand_sum / brand_*.
4. Выручка = revenue_series / dashboard / profit_* / brand_sales, не сумма сырых отгрузок.
5. Многошаговые вопросы: вызови tool → дождись result → следующий tool с РЕАЛЬНЫМИ id/именами из result.
6. Запрещены placeholder в аргументах (<<...>>, step_1, TODO). Для customer_purchases бери counterparty_id из top_counterparties.best.id или items[0].id.
7. Если данных недостаточно — один уточняющий вопрос. Если вне возможностей tools — скажи честно.
8. store по умолчанию antrasha. «Весна-лето / ВЛ» → season=VL + year. Период «июль» без года = июль текущего года.
9. Категория/тип изделия (костюмы, рубашки, платья, обувь, аксессуары, верхняя одежда и любая группа товаров) —
   tool category_sales, НЕ brand_sales. gender=male|female если указан пол.
   Сравнение нескольких сезонов/лет — отдельный вызов category_sales на каждый year.
   Остатки в stock_items; итог: stock_units, stock_retail_sum. product_folders — какие папки МС сопоставлены.
"""


def _run_agent_loop(
    settings: Settings,
    *,
    question: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    model = (settings.warehouse_ai_writer_model or settings.anthropic_model or "claude-sonnet-4-6").strip()
    client = MoySkladAnalyticsClient(str(settings.moysklad_token).strip())
    usage: dict[str, int] = {}
    operations_run: list[str] = []
    cache_hits = 0
    tools_payload = anthropic_tools()

    messages: list[dict[str, Any]] = []
    for m in history[-6:]:
        messages.append({"role": m["role"], "content": m["content"][:6000]})
    messages.append({"role": "user", "content": question[:12000]})

    final_text = ""
    stop_reason = None

    try:
        for round_i in range(MAX_TOOL_ROUNDS):
            data = _anthropic_raw(
                settings,
                model=model,
                payload={
                    "model": model,
                    "max_tokens": max(1024, int(settings.anthropic_max_tokens or 8192)),
                    "system": _agent_system(),
                    "tools": tools_payload,
                    "messages": messages,
                },
            )
            _merge_usage(usage, data.get("usage"))
            stop_reason = data.get("stop_reason")
            content = data.get("content") if isinstance(data.get("content"), list) else []

            tool_uses = [
                b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"
            ]
            text_parts = [
                str(b.get("text") or "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
            ]
            if text_parts:
                final_text = "\n\n".join(text_parts).strip()

            log.info(
                "agent round=%s stop=%s tools=%s",
                round_i,
                stop_reason,
                [t.get("name") for t in tool_uses],
            )

            if not tool_uses:
                break

            # Append assistant turn with full content (incl. tool_use)
            messages.append({"role": "assistant", "content": content})

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                name = str(tu.get("name") or "")
                tool_use_id = str(tu.get("id") or "")
                raw_input = tu.get("input") if isinstance(tu.get("input"), dict) else {}
                if name not in KNOWN_OPERATION_IDS:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": True,
                            "content": f"Unknown tool: {name}",
                        }
                    )
                    continue
                try:
                    args = _sanitize_tool_input(name, raw_input)
                    result = run_operation(client, name, args, use_cache=True)
                    if result.get("cache_hit"):
                        cache_hits += 1
                    operations_run.append(name)
                    compact = _compact_tool_result(result)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(compact, ensure_ascii=False, default=str)[:80_000],
                        }
                    )
                except (MoySkladAnalyticsError, ValueError, LookupError) as e:
                    log.warning("tool %s error: %s input=%s", name, e, raw_input)
                    operations_run.append(name)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": True,
                            "content": str(e),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

            if stop_reason == "end_turn":
                break
        else:
            if not final_text:
                final_text = (
                    "Достигнут лимит шагов анализа. Уточните вопрос или сузьте период/бренд."
                )
    finally:
        client.close()

    if not final_text:
        final_text = (
            "Не удалось сформировать ответ. Попробуйте переформулировать вопрос "
            "или выбрать готовый таб."
        )

    return {
        "reply": final_text,
        "model": model,
        "tools_used": operations_run,
        "operations": operations_run,
        "stop_reason": stop_reason or "end_turn",
        "usage": usage,
        "continues": 0,
        "mode": "semantic_agent",
        "cache_hits": cache_hits,
        "plan": {"type": "tool_loop", "rounds": MAX_TOOL_ROUNDS},
    }


def _run_preset(
    settings: Settings,
    *,
    preset_id: str,
    question: str,
) -> dict[str, Any]:
    steps = PRESET_PLANS.get(preset_id) or []
    client = MoySkladAnalyticsClient(str(settings.moysklad_token).strip())
    facts: list[dict[str, Any]] = []
    operations_run: list[str] = []
    cache_hits = 0
    usage: dict[str, int] = {}
    try:
        for raw in steps:
            op = raw["operation"]
            args = _fill_preset_args(op, dict(raw.get("args") or {}), preset_id=preset_id)
            result = run_operation(client, op, args, use_cache=True)
            if result.get("cache_hit"):
                cache_hits += 1
            operations_run.append(op)
            facts.append(_compact_tool_result(result))
    finally:
        client.close()

    model = (settings.warehouse_ai_writer_model or settings.anthropic_model or "claude-sonnet-4-6").strip()
    data = _anthropic_raw(
        settings,
        model=model,
        payload={
            "model": model,
            "max_tokens": max(1024, int(settings.anthropic_max_tokens or 8192)),
            "system": (
                "Ты аналитик ANTRASHA. Ответь по-русски Markdown по facts. "
                "Не выдумывай цифры. Деньги в ₽."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "facts": facts},
                        ensure_ascii=False,
                        default=str,
                    )[:120_000],
                }
            ],
        },
    )
    _merge_usage(usage, data.get("usage"))
    texts = []
    for b in data.get("content") or []:
        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
            texts.append(str(b["text"]))
    reply = "\n\n".join(texts).strip() or "Нет данных для ответа."
    return {
        "reply": reply,
        "model": model,
        "tools_used": operations_run,
        "operations": operations_run,
        "stop_reason": data.get("stop_reason") or "end_turn",
        "usage": usage,
        "continues": 0,
        "mode": "semantic_preset",
        "cache_hits": cache_hits,
        "plan": {"type": "preset", "id": preset_id},
    }


def chat_semantic(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    preset_id: str | None = None,
) -> dict[str, Any]:
    if not semantic_configured(settings):
        raise RuntimeError(
            "Semantic AI не настроен (нужны ANTHROPIC_API_KEY и MOYSKLAD_TOKEN)"
        )

    question = messages[-1]["content"]
    if preset_id:
        from app.services.warehouse_ai import WAREHOUSE_AI_PRESETS

        preset = next((p for p in WAREHOUSE_AI_PRESETS if p["id"] == preset_id), None)
        if preset:
            question = f"{preset['title']}: {preset['description']}"
        if preset_id in PRESET_PLANS:
            return _run_preset(settings, preset_id=preset_id, question=question)

    return _run_agent_loop(
        settings,
        question=question,
        history=messages[:-1],
    )

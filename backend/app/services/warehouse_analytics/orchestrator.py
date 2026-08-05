"""Orchestrator: Haiku router → MoySklad operations → Sonnet writer."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from app.config import Settings
from app.services.warehouse_analytics.catalog import (
    KNOWN_OPERATION_IDS,
    catalog_for_prompt,
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
MAX_PLAN_STEPS = 3
# 529 Overloaded / 503 — временные; ретраим с backoff.
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 529})
_MAX_RETRIES = 4
_RETRY_BASE_SEC = 1.5

# Пресет → готовый план (без router).
PRESET_PLANS: dict[str, list[dict[str, Any]]] = {
    "stock_overview": [
        {"operation": "stock_snapshot", "args": {"store": "antrasha", "mode": "positive", "limit": 15}},
    ],
    "low_stock": [
        {"operation": "stock_snapshot", "args": {"store": "antrasha", "mode": "low", "limit": 20}},
    ],
    "sales_week": [
        {"operation": "revenue_series", "args": {"interval": "day"}},  # dates filled in execute
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


def _anthropic_messages(
    settings: Settings,
    *,
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, dict[str, int], str | None]:
    api_key = str(settings.anthropic_api_key).strip()
    timeout = max(30.0, float(settings.anthropic_http_timeout or 180.0))
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    proxies = _proxies(settings)
    data: Any = {}
    res: requests.Response | None = None
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
                delay = _RETRY_BASE_SEC * (2**attempt)
                log.warning(
                    "anthropic network error attempt=%s/%s sleep=%.1fs: %s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    delay,
                    e,
                )
                time.sleep(delay)
                continue
            raise RuntimeError(f"Сеть Anthropic: {e}") from e

        try:
            data = res.json()
        except ValueError:
            data = {"raw": (res.text or "")[:400]}

        if res.status_code < 400:
            break

        detail = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(detail, dict):
            msg = detail.get("message") or str(detail)
        else:
            msg = str(detail)
        last_err = f"Anthropic HTTP {res.status_code}: {msg}"

        if res.status_code in _RETRYABLE_HTTP and attempt < _MAX_RETRIES:
            delay = _RETRY_BASE_SEC * (2**attempt)
            # Respect Retry-After if present
            ra = res.headers.get("retry-after")
            if ra:
                try:
                    delay = max(delay, float(ra))
                except ValueError:
                    pass
            log.warning(
                "anthropic retryable HTTP %s attempt=%s/%s sleep=%.1fs model=%s",
                res.status_code,
                attempt + 1,
                _MAX_RETRIES + 1,
                delay,
                model,
            )
            time.sleep(delay)
            continue

        hint = ""
        if res.status_code == 529:
            hint = " — Anthropic перегружен, подождите минуту и повторите запрос."
        raise RuntimeError(f"{last_err}{hint}")

    assert res is not None and res.status_code < 400
    texts = []
    for block in data.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            texts.append(str(block["text"]))
    usage: dict[str, int] = {}
    _merge_usage(usage, data.get("usage"))
    return "\n".join(texts).strip(), usage, data.get("stop_reason")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Router не вернул JSON")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Router JSON не объект")
    return obj


def _fill_default_dates(args: dict[str, Any], *, interval: str | None = None) -> dict[str, Any]:
    """Подставить даты для пресетов, если router/пресет не указал."""
    from datetime import date, timedelta

    today = datetime.now(_TZ).date()
    out = dict(args)
    if "date_to" not in out and "date_from" not in out and "season" not in out:
        if interval == "month" or out.get("interval") == "month":
            # 12 full months + current
            start = date(today.year, today.month, 1)
            # go back 12 months
            y, m = today.year, today.month - 11
            while m <= 0:
                m += 12
                y -= 1
            out["date_from"] = date(y, m, 1).isoformat()
            out["date_to"] = today.isoformat()
            out.setdefault("interval", "month")
        elif "period" in out and out["period"] == "week":
            pass
        else:
            # last 7 days for week-ish revenue
            if out.get("interval") == "day" and not out.get("date_from"):
                out["date_from"] = (today - timedelta(days=6)).isoformat()
                out["date_to"] = today.isoformat()
            elif not out.get("date_from"):
                out["date_from"] = date(today.year, today.month, 1).isoformat()
                out["date_to"] = today.isoformat()
    return out


def route_question(
    settings: Settings,
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    today = datetime.now(_TZ).date().isoformat()
    system = f"""\
Ты router аналитики магазина ANTRASHA (МойСклад).
Сегодня (Europe/Moscow): {today}.
Верни ТОЛЬКО JSON без markdown.

Формат успеха:
{{"steps":[{{"operation":"...","args":{{...}}}}], "rationale":"кратко"}}

Уточнение:
{{"clarify":"вопрос пользователю"}}

Не умеем:
{{"unsupported":"почему"}}

Правила:
- Максимум {MAX_PLAN_STEPS} steps.
- Бренд = поставщик; не путать с папкой.
- Выручка = revenue_series / dashboard_period / profit_*, не «суммируй отгрузки».
- Для «лучший покупатель + разрез покупок»: top_counterparties затем customer_purchases (подставь counterparty_name из топа нельзя заранее — сначала только top_counterparties; если в истории уже есть имя/id клиента — сразу customer_purchases).
- Даты YYYY-MM-DD. Если период «июль» без года — июль текущего года (если ещё не наступил — прошлый июль относительно {today}).
- store по умолчанию antrasha.

Доступные operation:
{catalog_for_prompt()}
"""
    msgs: list[dict[str, str]] = []
    if history:
        # last few turns for context
        for m in history[-6:]:
            msgs.append({"role": m["role"], "content": m["content"][:4000]})
    msgs.append({"role": "user", "content": question[:8000]})
    model = (settings.warehouse_ai_router_model or "claude-haiku-4-5").strip()
    text, usage, _ = _anthropic_messages(
        settings,
        model=model,
        system=system,
        messages=msgs,
        max_tokens=1024,
    )
    plan = _extract_json(text)
    return plan, usage


def _normalize_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return []
    out = []
    for step in steps[:MAX_PLAN_STEPS]:
        if not isinstance(step, dict):
            continue
        op = str(step.get("operation") or "").strip()
        if op not in KNOWN_OPERATION_IDS:
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        out.append({"operation": op, "args": _fill_default_dates(args, interval=args.get("interval"))})
    return out


def write_answer(
    settings: Settings,
    *,
    question: str,
    facts: list[dict[str, Any]],
) -> tuple[str, dict[str, int], str]:
    model = (settings.warehouse_ai_writer_model or settings.anthropic_model or "claude-sonnet-4-6").strip()
    system = """\
Ты аналитик магазина одежды ANTRASHA. Отвечай по-русски, кратко, Markdown (таблицы GFM).
Используй ТОЛЬКО переданные facts. Не выдумывай цифры. Укажи периоды и допущения одной строкой.
Если facts с ошибкой — скажи прямо. Деньги в ₽.
"""
    payload = {
        "question": question,
        "facts": facts,
    }
    text, usage, _ = _anthropic_messages(
        settings,
        model=model,
        system=system,
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str)[:120_000],
            }
        ],
        max_tokens=max(1024, int(settings.anthropic_max_tokens or 8192)),
    )
    return text, usage, model


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

    usage_total: dict[str, int] = {}
    operations_run: list[str] = []
    cache_hits = 0

    # 1) Plan
    if preset_id and preset_id in PRESET_PLANS:
        steps = []
        for raw in PRESET_PLANS[preset_id]:
            args = _fill_default_dates(dict(raw.get("args") or {}), interval=(raw.get("args") or {}).get("interval"))
            # week revenue dates
            if preset_id == "sales_week" and raw["operation"] == "revenue_series":
                from datetime import timedelta

                today = datetime.now(_TZ).date()
                args["date_from"] = (today - timedelta(days=6)).isoformat()
                args["date_to"] = today.isoformat()
                args["interval"] = "day"
            if preset_id == "sales_month" and raw["operation"] == "revenue_series":
                today = datetime.now(_TZ).date()
                args["date_from"] = today.replace(day=1).isoformat()
                args["date_to"] = today.isoformat()
                args["interval"] = "day"
            steps.append({"operation": raw["operation"], "args": args})
        plan = {"steps": steps, "rationale": f"preset:{preset_id}"}
    else:
        plan, u_route = route_question(settings, question, history=messages[:-1])
        _merge_usage(usage_total, u_route)
        if plan.get("clarify"):
            return {
                "reply": str(plan["clarify"]),
                "model": settings.warehouse_ai_router_model or "claude-haiku-4-5",
                "tools_used": [],
                "operations": [],
                "stop_reason": "clarify",
                "usage": usage_total,
                "continues": 0,
                "mode": "semantic",
            }
        if plan.get("unsupported"):
            return {
                "reply": f"Пока не умею это надёжно посчитать: {plan['unsupported']}",
                "model": settings.warehouse_ai_router_model or "claude-haiku-4-5",
                "tools_used": [],
                "operations": [],
                "stop_reason": "unsupported",
                "usage": usage_total,
                "continues": 0,
                "mode": "semantic",
            }
        steps = _normalize_steps(plan)
        if not steps:
            return {
                "reply": "Не смог сопоставить вопрос с доступными операциями. Уточните период, бренд или метрику.",
                "model": settings.warehouse_ai_router_model or "claude-haiku-4-5",
                "tools_used": [],
                "operations": [],
                "stop_reason": "empty_plan",
                "usage": usage_total,
                "continues": 0,
                "mode": "semantic",
            }

    # 2) Execute
    client = MoySkladAnalyticsClient(str(settings.moysklad_token).strip())
    facts: list[dict[str, Any]] = []
    try:
        for i, step in enumerate(steps):
            op = step["operation"]
            args = dict(step["args"])
            # Chain: after top_counterparties, if next is customer_purchases without id — inject top name
            if (
                op == "customer_purchases"
                and not args.get("counterparty_id")
                and not args.get("counterparty_name")
            ):
                for prev in facts:
                    items = prev.get("items") if isinstance(prev.get("items"), list) else []
                    if prev.get("operation") == "top_counterparties" and items:
                        top = items[0]
                        if top.get("id"):
                            args["counterparty_id"] = top["id"]
                        elif top.get("name"):
                            args["counterparty_name"] = top["name"]
                        break

            try:
                result = run_operation(client, op, args, use_cache=True)
                if result.get("cache_hit"):
                    cache_hits += 1
                operations_run.append(op)
                facts.append(result)
            except (MoySkladAnalyticsError, ValueError, LookupError) as e:
                log.warning("operation %s failed: %s", op, e)
                facts.append({"operation": op, "error": str(e), "args": args})
                operations_run.append(op)

            # Auto-extend: if single top_counterparties and question asks for breakdown — fetch purchases
            if (
                i == len(steps) - 1
                and op == "top_counterparties"
                and len(steps) < MAX_PLAN_STEPS
                and re.search(r"размер|пол|марку|бренд|покупк|разрез|анализ", question, re.I)
            ):
                items = facts[-1].get("items") if isinstance(facts[-1].get("items"), list) else []
                if items and items[0].get("id"):
                    try:
                        extra = run_operation(
                            client,
                            "customer_purchases",
                            {
                                "counterparty_id": items[0]["id"],
                                "date_from": facts[-1].get("date_from"),
                                "date_to": facts[-1].get("date_to"),
                            },
                        )
                        if extra.get("cache_hit"):
                            cache_hits += 1
                        operations_run.append("customer_purchases")
                        facts.append(extra)
                    except (MoySkladAnalyticsError, ValueError, LookupError) as e:
                        facts.append({"operation": "customer_purchases", "error": str(e)})
    finally:
        client.close()

    # 3) Writer
    reply, u_write, model = write_answer(settings, question=question, facts=facts)
    _merge_usage(usage_total, u_write)
    if not reply:
        reply = "Не удалось сформировать ответ по данным."

    log.info(
        "warehouse_semantic ops=%s cache_hits=%s usage=%s",
        operations_run,
        cache_hits,
        usage_total,
    )
    return {
        "reply": reply,
        "model": model,
        "tools_used": operations_run,
        "operations": operations_run,
        "stop_reason": "end_turn",
        "usage": usage_total,
        "continues": 0,
        "mode": "semantic",
        "cache_hits": cache_hits,
        "plan": plan if isinstance(plan, dict) else {"steps": steps},
    }

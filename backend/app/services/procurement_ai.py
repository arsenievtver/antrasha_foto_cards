"""Диалоговый агент закупок.

Отдельный от ассистента МойСклад: свои инструменты, свой промпт, своя история.
Чтение доступно всем с правом «Товар». Запись — только если у этого человека
активный MCP-ключ со скоупом write. Удаления в инструментах нет.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings
from app.database import SessionLocal
from app.deps import AdminPrincipal
from app.mcp_procurement.registry import (
    SCOPE_READ,
    SCOPE_WRITE,
    ToolArgumentError,
    ToolPermissionError,
    call_tool,
    get_tool,
    list_tools,
)
from app.services.mcp_keys import McpActor, actor_from_key, get_active_key_for_principal
from app.services.warehouse_analytics.orchestrator import _anthropic_raw

import app.mcp_procurement.tools  # noqa: F401

log = logging.getLogger("app.procurement_ai")

_TZ = ZoneInfo("Europe/Moscow")
MAX_TOOL_ROUNDS = 8
_PLACEHOLDER_RE = re.compile(r"<<|>>|\bTODO\b|placeholder|from_previous|\{\{", re.I)

PRESETS: list[dict[str, str]] = [
    {
        "id": "shipments",
        "title": "Поставки сезона",
        "description": "Доставлено, в пути и остаток по сезонам PWA",
        "prompt": (
            "Сводка поставок по сезонам, отмеченным для PWA. "
            "По каждому: заказано, доставлено, что числится в пути, сколько осталось поставить. "
            "Для сезона с наибольшим остатком — разбивка по брендам и график."
        ),
    },
    {
        "id": "balances",
        "title": "Осталось поставить",
        "description": "Бренды, у которых поставка ещё не закрыла заказ",
        "prompt": (
            "По текущим сезонам PWA покажи бренды, у которых осталось поставить больше нуля. "
            "Таблица и график остатка в евро. В пути отдельно, не смешивай с доставленным."
        ),
    },
    {
        "id": "prepayments",
        "title": "Предоплаты",
        "description": "Сроки, просрочки и остаток предоплаты",
        "prompt": (
            "Картина предоплат по сезонам дашборда: план, факт, остаток, просрочка. "
            "График остатка по брендам или сезонам, если точек больше одной."
        ),
    },
    {
        "id": "fx",
        "title": "Курс EUR",
        "description": "Действующий курс и последние периоды",
        "prompt": (
            "Какой курс EUR/RUB действует сегодня и какие периоды заданы последними. "
            "Если периодов несколько, график значения курса по дате начала."
        ),
    },
]


def _today() -> datetime:
    return datetime.now(_TZ)


def effective_scope(key_scope: str | None) -> str:
    return SCOPE_WRITE if key_scope == SCOPE_WRITE else SCOPE_READ


def anthropic_tools(scope: str) -> list[dict[str, Any]]:
    tools = []
    for item in list_tools(scope):
        tools.append(
            {
                "name": item["name"],
                "description": item["description"],
                "input_schema": item["inputSchema"],
            }
        )
    return tools


def system_prompt(*, can_write: bool) -> str:
    today = _today().date().isoformat()
    if can_write:
        access = (
            "Ключ этого человека выпущен с правом записи: можно создавать и менять "
            "сезоны, бренды, заказы, оплаты, поставки и курс. Удалять нельзя — "
            "такого инструмента нет, удаление только вручную в админке."
        )
    else:
        access = (
            "Сейчас только чтение. Ключа с правом записи нет, поэтому создавать и "
            "менять записи нельзя. Если просят записать — скажи, что нужен ключ MCP "
            "с галочкой «Разрешить изменять данные» на странице «Ключ MCP», и не "
            "вызывай инструменты записи."
        )
    return f"""\
Ты агент закупок магазина ANTRASHA. Сегодня (Europe/Moscow): {today}.

Это не МойСклад и не продажи магазина. Твои данные — только закупки самого проекта:
сезоны, бренды, заказы брендам, оплаты брендам, входящие поставки и курс EUR/RUB.
Слова здесь значат именно это:
- бренд — справочник брендов закупок, не поставщик МойСклад;
- сезон — сезон заказа (например «Осень-зима 2026/2027»), не метка в артикуле;
- заказ — заказ бренду, не заказ покупателя;
- поставка — входящая поставка от бренда в евро; is_delivered=false значит «в пути»
  и не входит в «доставлено» / «осталось поставить»;
- оплата — оплата бренду, kind=prepayment (предоплата) или kind=main (основная).

{access}

## Как отвечать
1. Сначала вызови инструменты, потом один итоговый ответ по-русски.
2. Цифры только из результатов инструментов. Не выдумывай суммы, даты и названия.
3. Идентификаторы бери из list_seasons, list_brands, list_categories. По имени фильтровать нельзя, имя можно сопоставить со списком.
4. Суммы заказов, оплат и поставок — в евро. Логистика поставки — в рублях. Курс документа, если его не передали, подставляется из справочника на дату.
5. Если вопрос про аналитику и сравниваешь хотя бы два числа, кроме таблицы Markdown вставь график отдельным блоком. Ровно такой формат, без текста вокруг JSON внутри блока:

```chart
{{"type":"bar","title":"Короткий заголовок","unit":"€","items":[{{"label":"Duno","value":7139.5}}]}}
```

type: bar — суммы, остатки и даты; donut — доли одного целого. unit: €, ₽, кг или пустая строка. value — число, не строка. Не больше 12 пунктов. Таблицу с теми же цифрами всё равно оставь.

## Запись
Перед create_* и update_* составь поля, которые попадут в запись.
Обязательно должны быть известны:
- сезон и бренд (достаточно названия, id найди сам);
- заказ: сумма или строки категорий; если речь о предоплате — сумма и срок;
- оплата: дата, сумма в евро и вид (предоплата или основная);
- поставка: дата, сумма в евро и статус (уже приехала или ещё в пути);
- курс: дата начала и значение; если конец периода не назван и не сказано «бессрочно» — спроси;
- новый сезон: название и код.

Если любого обязательного поля нет — не вызывай инструмент. Одним сообщением перечисли, чего не хватает, и дождись ответа.
Не подставляй от себя вес, логистику, комментарий, пол, предоплату и курс документа.
Курс оплаты и поставки можно не передавать: справочник подставит его сам, а в ответе после записи назови, какой курс встал.
В update передавай только поля, которые человек явно меняет. Не затирай остальные.
Половинчатую запись не создавай.
"""


def _actor_for(principal: AdminPrincipal, key) -> tuple[McpActor, bool]:
    if key is not None and key.scope == SCOPE_WRITE:
        return actor_from_key(key), True
    if key is not None:
        return actor_from_key(key), False
    return (
        McpActor(
            key_id=uuid.UUID(int=0),
            owner_role=principal.role,
            user_id=principal.user.id if principal.user else None,
            scope=SCOPE_READ,
        ),
        False,
    )


def _reject_placeholders(name: str, arguments: dict) -> None:
    for key, value in arguments.items():
        if isinstance(value, str) and _PLACEHOLDER_RE.search(value):
            raise ToolArgumentError(
                f"В {name}.{key} нельзя оставлять заглушку {value!r}. "
                "Возьми значение из предыдущего результата или спроси человека."
            )


def _run_tool(db: Session, actor: McpActor, name: str, arguments: dict) -> Any:
    item = get_tool(name)
    if item is None:
        raise ToolArgumentError(f"Неизвестный инструмент: {name}")
    _reject_placeholders(name, arguments)
    return call_tool(item, db, actor, arguments)


def _merge_usage(total: dict[str, int], usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total[key] = total.get(key, 0) + value


def chat_procurement(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    principal: AdminPrincipal,
) -> dict[str, Any]:
    if not (settings.anthropic_api_key and str(settings.anthropic_api_key).strip()):
        raise RuntimeError("Агент закупок не настроен: нужен ANTHROPIC_API_KEY")

    model = (
        settings.warehouse_ai_writer_model or settings.anthropic_model or "claude-sonnet-4-6"
    ).strip()
    question = messages[-1]["content"]
    history = messages[:-1]

    db = SessionLocal()
    try:
        key = get_active_key_for_principal(db, principal)
        actor, can_write = _actor_for(principal, key)
        tools = anthropic_tools(actor.scope)
        api_messages: list[dict[str, Any]] = [
            {"role": m["role"], "content": m["content"][:8000]} for m in history[-8:]
        ]
        api_messages.append({"role": "user", "content": question[:12000]})

        usage: dict[str, int] = {}
        tools_used: list[str] = []
        final_text = ""
        stop_reason = None

        for round_i in range(MAX_TOOL_ROUNDS):
            data = _anthropic_raw(
                settings,
                model=model,
                payload={
                    "model": model,
                    "max_tokens": max(1024, int(settings.anthropic_max_tokens or 8192)),
                    "system": system_prompt(can_write=can_write),
                    "tools": tools,
                    "messages": api_messages,
                },
            )
            _merge_usage(usage, data.get("usage"))
            stop_reason = data.get("stop_reason")
            content = data.get("content") if isinstance(data.get("content"), list) else []
            tool_uses = [
                block
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_use"
            ]
            text_parts = [
                str(block.get("text") or "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
            ]
            if text_parts:
                final_text = "\n\n".join(text_parts).strip()

            log.info(
                "procurement_ai round=%s stop=%s write=%s tools=%s",
                round_i,
                stop_reason,
                can_write,
                [block.get("name") for block in tool_uses],
            )
            if not tool_uses:
                break

            api_messages.append({"role": "assistant", "content": content})
            tool_results = []
            for block in tool_uses:
                name = str(block.get("name") or "")
                tool_use_id = str(block.get("id") or "")
                raw_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                tools_used.append(name)
                try:
                    payload = _run_tool(db, actor, name, raw_input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(payload, ensure_ascii=False, default=str)[
                                :80_000
                            ],
                        }
                    )
                except (ToolArgumentError, ToolPermissionError) as exc:
                    db.rollback()
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": True,
                            "content": str(exc),
                        }
                    )
                except Exception:
                    db.rollback()
                    log.exception("procurement_ai tool %s failed", name)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": True,
                            "content": f"Инструмент {name} завершился с ошибкой.",
                        }
                    )
            api_messages.append({"role": "user", "content": tool_results})
        else:
            if not final_text:
                final_text = (
                    "Достигнут лимит шагов. Уточните сезон, бренд или что именно записать."
                )
    finally:
        db.close()

    if not final_text:
        final_text = "Не удалось сформировать ответ. Переформулируйте вопрос."

    return {
        "reply": final_text,
        "model": model,
        "tools_used": tools_used,
        "stop_reason": stop_reason or "end_turn",
        "usage": usage,
        "can_write": can_write,
    }


def status_for(principal: AdminPrincipal) -> dict[str, Any]:
    db = SessionLocal()
    try:
        key = get_active_key_for_principal(db, principal)
    finally:
        db.close()
    key_scope = key.scope if key is not None else None
    scope = effective_scope(key_scope)
    return {
        "key_present": key is not None,
        "key_scope": key_scope,
        "can_write": scope == SCOPE_WRITE,
        "tools_count": len(list_tools(scope)),
    }

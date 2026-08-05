"""Tests for agentic semantic orchestrator (no live Anthropic/MS)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.services.warehouse_analytics.catalog import anthropic_tools, KNOWN_OPERATION_IDS
from app.services.warehouse_analytics.operations import run_operation
from app.services.warehouse_analytics.orchestrator import (
    _sanitize_tool_input,
    chat_semantic,
)


class ToolCatalogTests(unittest.TestCase):
    def test_tools_match_ops(self):
        tools = anthropic_tools()
        names = {t["name"] for t in tools}
        self.assertEqual(names, set(KNOWN_OPERATION_IDS))
        for t in tools:
            self.assertIn("input_schema", t)
            self.assertEqual(t["input_schema"].get("type"), "object")


class SanitizeTests(unittest.TestCase):
    def test_rejects_placeholder(self):
        with self.assertRaises(ValueError):
            _sanitize_tool_input(
                "customer_purchases",
                {"counterparty_name": "<<top_counterparty_from_step_1>>"},
            )

    def test_accepts_uuid(self):
        out = _sanitize_tool_input(
            "customer_purchases",
            {"counterparty_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
        )
        self.assertEqual(out["counterparty_id"], "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class AgentLoopTests(unittest.TestCase):
    def test_tool_then_answer(self):
        """Модель вызывает top_counterparties, получает result, отвечает текстом."""
        settings = MagicMock()
        settings.anthropic_api_key = "sk-test"
        settings.moysklad_token = "ms-test"
        settings.anthropic_https_proxy = None
        settings.anthropic_http_timeout = 30
        settings.anthropic_max_tokens = 1024
        settings.warehouse_ai_writer_model = "claude-sonnet-4-6"
        settings.anthropic_model = "claude-sonnet-4-6"

        round1 = {
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "top_counterparties",
                    "input": {
                        "date_from": "2026-07-01",
                        "date_to": "2026-07-31",
                        "limit": 10,
                    },
                }
            ],
        }
        round2 = {
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 200, "output_tokens": 80},
            "content": [
                {
                    "type": "text",
                    "text": "Лучший покупатель — Ильичев (100000 ₽).",
                }
            ],
        }

        op_result = {
            "operation": "top_counterparties",
            "best": {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "name": "Ильичев", "sell_sum": 100000},
            "items": [
                {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "name": "Ильичев", "sell_sum": 100000},
                {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "name": "Абашева", "sell_sum": 2300},
            ],
            "cache_hit": False,
        }

        with (
            patch(
                "app.services.warehouse_analytics.orchestrator._anthropic_raw",
                side_effect=[round1, round2],
            ) as raw,
            patch(
                "app.services.warehouse_analytics.orchestrator.run_operation",
                return_value=op_result,
            ) as run_op,
            patch(
                "app.services.warehouse_analytics.orchestrator.MoySkladAnalyticsClient",
            ) as client_cls,
        ):
            client_cls.return_value = MagicMock()
            out = chat_semantic(
                settings,
                messages=[
                    {
                        "role": "user",
                        "content": "Кто лучший покупатель был в июле — анализ покупок",
                    }
                ],
            )

        self.assertEqual(out["mode"], "semantic_agent")
        self.assertIn("Ильичев", out["reply"])
        self.assertEqual(out["operations"], ["top_counterparties"])
        self.assertEqual(raw.call_count, 2)
        # второй вызов Anthropic должен получить tool_result с реальными данными
        second_payload = raw.call_args_list[1].kwargs["payload"]
        msgs = second_payload["messages"]
        self.assertEqual(msgs[-1]["role"], "user")
        tr = msgs[-1]["content"][0]
        self.assertEqual(tr["type"], "tool_result")
        body = json.loads(tr["content"])
        self.assertEqual(body["best"]["name"], "Ильичев")
        run_op.assert_called_once()


class MultiStepBindingTests(unittest.TestCase):
    def test_second_tool_gets_real_id_from_first_result(self):
        """Механизм: шаг2 не планируется заранее — id берётся из tool_result шага1."""
        settings = MagicMock()
        settings.anthropic_api_key = "sk-test"
        settings.moysklad_token = "ms-test"
        settings.anthropic_https_proxy = None
        settings.anthropic_http_timeout = 30
        settings.anthropic_max_tokens = 1024
        settings.warehouse_ai_writer_model = "claude-sonnet-4-6"
        settings.anthropic_model = "claude-sonnet-4-6"

        buyer_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        round1 = {
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 10},
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "top_counterparties",
                    "input": {"date_from": "2026-07-01", "date_to": "2026-07-31", "limit": 5},
                }
            ],
        }
        round2 = {
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 20},
            "content": [
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "customer_purchases",
                    "input": {
                        "counterparty_id": buyer_id,
                        "date_from": "2026-07-01",
                        "date_to": "2026-07-31",
                    },
                }
            ],
        }
        round3 = {
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 30, "output_tokens": 40},
            "content": [{"type": "text", "text": "Разбор покупок Ильичева готов."}],
        }

        def run_side_effect(_client, name, args, use_cache=True):
            if name == "top_counterparties":
                return {
                    "operation": name,
                    "best": {"id": buyer_id, "name": "Ильичев", "sell_sum": 100000},
                    "items": [{"id": buyer_id, "name": "Ильичев", "sell_sum": 100000}],
                }
            if name == "customer_purchases":
                self.assertEqual(args["counterparty_id"], buyer_id)
                return {
                    "operation": name,
                    "counterparty": {"id": buyer_id, "name": "Ильичев"},
                    "lines": [{"name": "Пальто", "sum": 50000}],
                }
            raise AssertionError(name)

        with (
            patch(
                "app.services.warehouse_analytics.orchestrator._anthropic_raw",
                side_effect=[round1, round2, round3],
            ),
            patch(
                "app.services.warehouse_analytics.orchestrator.run_operation",
                side_effect=run_side_effect,
            ),
            patch(
                "app.services.warehouse_analytics.orchestrator.MoySkladAnalyticsClient",
            ) as client_cls,
        ):
            client_cls.return_value = MagicMock()
            out = chat_semantic(
                settings,
                messages=[{"role": "user", "content": "Лучший покупатель июля и его покупки"}],
            )

        self.assertEqual(out["operations"], ["top_counterparties", "customer_purchases"])
        self.assertIn("Ильичева", out["reply"])

    def test_placeholder_error_returned_to_model(self):
        settings = MagicMock()
        settings.anthropic_api_key = "sk-test"
        settings.moysklad_token = "ms-test"
        settings.anthropic_https_proxy = None
        settings.anthropic_http_timeout = 30
        settings.anthropic_max_tokens = 1024
        settings.warehouse_ai_writer_model = "claude-sonnet-4-6"
        settings.anthropic_model = "claude-sonnet-4-6"

        bad = {
            "stop_reason": "tool_use",
            "usage": {},
            "content": [
                {
                    "type": "tool_use",
                    "id": "bad1",
                    "name": "customer_purchases",
                    "input": {"counterparty_name": "<<top_counterparty_from_step_1>>"},
                }
            ],
        }
        good = {
            "stop_reason": "end_turn",
            "usage": {},
            "content": [{"type": "text", "text": "Нужен id из предыдущего результата."}],
        }

        with (
            patch(
                "app.services.warehouse_analytics.orchestrator._anthropic_raw",
                side_effect=[bad, good],
            ) as raw,
            patch(
                "app.services.warehouse_analytics.orchestrator.run_operation",
            ) as run_op,
            patch(
                "app.services.warehouse_analytics.orchestrator.MoySkladAnalyticsClient",
            ) as client_cls,
        ):
            client_cls.return_value = MagicMock()
            out = chat_semantic(
                settings,
                messages=[{"role": "user", "content": "покупки лучшего"}],
            )

        run_op.assert_not_called()
        err_msg = raw.call_args_list[1].kwargs["payload"]["messages"][-1]["content"][0]
        self.assertTrue(err_msg.get("is_error"))
        self.assertIn("placeholder", err_msg["content"].lower())
        self.assertEqual(out["mode"], "semantic_agent")


class TopSortStillWorks(unittest.TestCase):
    def test_sort(self):
        client = MagicMock()
        client.get_rows.return_value = (
            [
                {
                    "sellSum": 230000,
                    "counterparty": {
                        "name": "Абашева",
                        "meta": {
                            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                        },
                    },
                },
                {
                    "sellSum": 10000000,
                    "counterparty": {
                        "name": "Ильичев",
                        "meta": {
                            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                        },
                    },
                },
            ],
            2,
        )
        out = run_operation(
            client,
            "top_counterparties",
            {"date_from": "2026-07-01", "date_to": "2026-07-31"},
            use_cache=False,
        )
        self.assertEqual(out["best"]["name"], "Ильичев")


if __name__ == "__main__":
    unittest.main()

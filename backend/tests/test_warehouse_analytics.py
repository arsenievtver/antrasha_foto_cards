"""Unit tests for warehouse semantic analytics (no live MoySklad)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.services.warehouse_analytics.cache import TtlCache, cache_key
from app.services.warehouse_analytics.catalog import KNOWN_OPERATION_IDS, catalog_for_prompt
from app.services.warehouse_analytics.ms_client import money_rub
from app.services.warehouse_analytics.operations import (
    matches_season_marker,
    run_operation,
    season_dates,
)
from app.services.warehouse_analytics.orchestrator import _sanitize_tool_input


class MoneyTests(unittest.TestCase):
    def test_kopecks(self):
        self.assertEqual(money_rub(90911200), 909112.0)
        self.assertEqual(money_rub(None), None)


class SeasonTests(unittest.TestCase):
    def test_dates_vl(self):
        a, b = season_dates("VL", 2025)
        self.assertEqual(a.isoformat(), "2025-02-01")
        self.assertEqual(b.isoformat(), "2025-08-31")

    def test_marker(self):
        self.assertTrue(matches_season_marker("Куртка ВЛ2025 /03.25", "VL", 2025))
        self.assertTrue(matches_season_marker("Пальто ОЗ24", "OZ", 2024))
        self.assertFalse(matches_season_marker("Куртка ВЛ2024", "VL", 2025))


class BrandSupplierTests(unittest.TestCase):
    def test_brand_key_strips_gender_suffix(self):
        from app.services.warehouse_analytics.operations import _brand_key

        self.assertEqual(_brand_key("DUNO(муж)"), "DUNO")
        self.assertEqual(_brand_key("TREVI (жен)"), "TREVI")

    def test_gender_from_short_path(self):
        from app.services.warehouse_analytics.operations import _gender_from_path

        self.assertEqual(_gender_from_path("Брюки, джинсы муж"), "male")
        self.assertEqual(_gender_from_path("Платья жен"), "female")

    def test_customer_purchases_uses_supplier_not_article(self):
        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"
        client.get.return_value = {
            "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "name": "Кирсанов",
        }

        def get_rows(path, params=None):
            if path == "/entity/demand":
                return ([], 0)
            if path == "/entity/retaildemand":
                return (
                    [
                        {
                            "moment": "2026-07-03 12:00:00",
                            "positions": {
                                "rows": [
                                    {
                                        "quantity": 1,
                                        "sum": 2040000,
                                        "assortment": {
                                            "name": "RAS TREVI/274/03.26 брюки 52",
                                            "article": "RAS TREVI/274/03.26",
                                            "pathName": "Брюки, джинсы муж",
                                            "supplier": {
                                                "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                                                "name": "DUNO(муж)",
                                            },
                                        },
                                    }
                                ]
                            },
                        }
                    ],
                    1,
                )
            return ([], 0)

        client.get_rows.side_effect = get_rows
        out = run_operation(
            client,
            "customer_purchases",
            {
                "counterparty_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            },
            use_cache=False,
        )
        self.assertEqual(out["lines"][0]["brand"], "DUNO")
        self.assertEqual(out["lines"][0]["supplier"], "DUNO(муж)")
        self.assertNotIn("TREVI", out["by_brand_sum"])
        self.assertEqual(out["by_brand_sum"]["DUNO"], 20400.0)
        self.assertEqual(out["lines"][0]["gender"], "male")


class CacheTests(unittest.TestCase):
    def test_roundtrip(self):
        c = TtlCache(default_ttl_sec=60)
        k = cache_key("stock_snapshot", {"store": "antrasha"})
        self.assertIsNone(c.get(k))
        c.set(k, {"ok": True})
        self.assertEqual(c.get(k), {"ok": True})


class CatalogTests(unittest.TestCase):
    def test_catalog_nonempty(self):
        self.assertIn("revenue_series", KNOWN_OPERATION_IDS)
        self.assertIn("customer_purchases", KNOWN_OPERATION_IDS)
        text = catalog_for_prompt()
        self.assertIn("revenue_series", text)


class SanitizeInputTests(unittest.TestCase):
    def test_rejects_unknown_keys_quietly_keeps_known(self):
        out = _sanitize_tool_input(
            "revenue_series",
            {"interval": "day", "date_from": "2026-07-01", "date_to": "2026-07-07"},
        )
        self.assertEqual(out["interval"], "day")

    def test_rejects_placeholder(self):
        with self.assertRaises(ValueError):
            _sanitize_tool_input(
                "customer_purchases",
                {"counterparty_name": "<<from_step_1>>"},
            )


class StockOperationTests(unittest.TestCase):
    def test_stock_snapshot(self):
        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"
        client.get_rows.return_value = (
            [
                {
                    "stock": 3,
                    "assortment": {"name": "Пальто", "article": "A1", "pathName": "Мужская коллекция"},
                }
            ],
            1,
        )
        out = run_operation(
            client,
            "stock_snapshot",
            {"store": "antrasha", "mode": "positive", "limit": 10},
            use_cache=False,
        )
        self.assertEqual(out["operation"], "stock_snapshot")
        self.assertEqual(out["items"][0]["name"], "Пальто")
        self.assertEqual(out["items"][0]["gender"], "male")


class TopCounterpartiesSortTests(unittest.TestCase):
    def test_sorts_by_sell_sum_desc(self):
        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"
        client.get_rows.return_value = (
            [
                {
                    "sellSum": 230000,
                    "profit": 159122,
                    "counterparty": {
                        "name": "Абашева",
                        "meta": {
                            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                        },
                    },
                },
                {
                    "sellSum": 10000000,
                    "profit": 5000000,
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
            {"date_from": "2026-07-01", "date_to": "2026-07-31", "limit": 5},
            use_cache=False,
        )
        self.assertEqual(out["items"][0]["name"], "Ильичев")
        self.assertEqual(out["best"]["name"], "Ильичев")
        self.assertEqual(out["items"][0]["sell_sum"], 100000.0)
        self.assertEqual(out["items"][0]["id"], "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class ProfitTopTests(unittest.TestCase):
    def test_profit_top(self):
        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"
        client.get_rows.return_value = (
            [
                {
                    "sellSum": 100000,
                    "profit": 40000,
                    "sellQuantity": 2,
                    "assortment": {"name": "Платье", "pathName": "Женская коллекция"},
                }
            ],
            1,
        )
        out = run_operation(
            client,
            "profit_top_products",
            {"date_from": "2026-07-01", "date_to": "2026-07-31", "limit": 5},
            use_cache=False,
        )
        self.assertEqual(out["items"][0]["sell_sum"], 1000.0)
        self.assertEqual(out["items"][0]["gender"], "female")


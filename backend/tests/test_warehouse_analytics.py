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
from app.services.warehouse_analytics.orchestrator import _normalize_steps


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


class NormalizeStepsTests(unittest.TestCase):
    def test_filters_unknown(self):
        steps = _normalize_steps(
            {
                "steps": [
                    {"operation": "revenue_series", "args": {"interval": "day"}},
                    {"operation": "hack_drop_table", "args": {}},
                ]
            }
        )
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["operation"], "revenue_series")


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


if __name__ == "__main__":
    unittest.main()

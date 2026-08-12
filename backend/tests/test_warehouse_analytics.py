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


class MsReportsFoundationTests(unittest.TestCase):
    def test_profit_filters_encode_supplier(self):
        from app.services.warehouse_analytics.ms_reports import ProfitFilters

        parts = ProfitFilters(
            supplier_ids=["85b76c4f-8e8b-11e9-9ff4-31500007fdb1"],
            store_ids=["1d4d5f44-7bb1-11e9-9109-f8fc00054224"],
        ).to_parts()
        joined = ";".join(parts)
        self.assertIn("supplier=https://api.moysklad.ru/api/remap/1.2/entity/counterparty/85b76c4f", joined)
        self.assertIn("store=https://api.moysklad.ru/api/remap/1.2/entity/store/1d4d5f44", joined)

    def test_stock_filters_supplier(self):
        from app.services.warehouse_analytics.ms_reports import StockFilters

        parts = StockFilters(
            supplier_ids=["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            quantity_mode="positiveOnly",
        ).to_parts()
        self.assertTrue(any(p.startswith("supplier=") for p in parts))
        self.assertIn("quantityMode=positiveOnly", parts)


class CategoryMatchTests(unittest.TestCase):
    def test_category_search_tokens(self):
        from app.services.warehouse_analytics.operations import _category_search_tokens

        self.assertIn("рубаш", _category_search_tokens("рубашки"))
        self.assertIn("джинс", _category_search_tokens("джинсы"))
        self.assertIn("верхняя одежда", _category_search_tokens("верхняя одежда"))

    def test_folder_matches_query(self):
        from app.services.warehouse_analytics.operations import _folder_matches_query

        self.assertTrue(_folder_matches_query("Рубашки", "Мужская коллекция", "рубашки"))
        self.assertTrue(_folder_matches_query("Брюки, джинсы муж", "Мужская коллекция", "джинсы"))
        self.assertTrue(_folder_matches_query("Платья/юбки", "Женская коллекция", "платье"))

    def test_matches_suit_name_and_path(self):
        from app.services.warehouse_analytics.operations import matches_product_category

        self.assertTrue(
            matches_product_category(
                "39095/380/03.19 костюмы",
                "Мужская коллекция/Костюмы муж",
                "костюм",
            )
        )
        self.assertTrue(matches_product_category("Костюм SCABAL", "Мужская коллекция/Костюмы муж", "костюмы"))
        self.assertTrue(
            matches_product_category("21-710N3/26 рубашка", "Мужская коллекция/Рубашки", "рубашки")
        )
        self.assertFalse(
            matches_product_category(
                "2215/018/2.16бр брюки (классика, Раздел.костюмы, 98)",
                None,
                "костюм",
            )
        )

    def test_category_sales_flow(self):
        from app.services.warehouse_analytics.operations import matches_product_category

        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"
        folder_id = "eec41100-9847-11eb-0a80-0616000ac009"
        product_id = "0189a452-b37b-11e9-9ff4-3150003a1cb8"

        def get_rows(path, params=None):
            params = params or {}
            filt = str(params.get("filter") or "")
            if path == "/entity/productfolder":
                return (
                    [
                        {
                            "id": folder_id,
                            "name": "Костюмы муж",
                            "pathName": "Мужская коллекция",
                        }
                    ],
                    1,
                )
            if path == "/entity/assortment":
                if "productfolder" in filt or "productFolder" in filt:
                    return (
                        [
                            {
                                "type": "product",
                                "id": product_id,
                                "name": "39095/380/02.25 костюмы",
                                "article": "39095/380/02.25",
                                "pathName": "Мужская коллекция/Костюмы муж",
                                "stock": 2,
                                "salePrice": 3405000,
                            }
                        ],
                        1,
                    )
                if "name~" in filt:
                    return ([], 0)
                return ([], 0)
            if path == "/report/profit/byproduct":
                return (
                    [
                        {
                            "assortment": {
                                "name": "39095/380/02.25 костюмы",
                                "article": "39095/380/02.25",
                                "pathName": "Мужская коллекция/Костюмы муж",
                                "meta": {"href": f"https://api.moysklad.ru/api/remap/1.2/entity/product/{product_id}"},
                            },
                            "sellQuantity": 3,
                            "sellSum": 9000000,
                            "profit": 3000000,
                        }
                    ],
                    1,
                )
            return [], 0

        client.get_rows.side_effect = get_rows
        out = run_operation(
            client,
            "category_sales",
            {"category": "костюм", "gender": "male", "season": "VL", "year": 2025},
            use_cache=False,
        )
        self.assertEqual(out["matched_sales_rows"], 1)
        self.assertEqual(out["total_sell_sum"], 90000.0)
        self.assertEqual(out["total_sell_quantity"], 3)
        self.assertIn("productfolder", out["method"])
        self.assertTrue(out["product_folders"])
        self.assertTrue(
            matches_product_category("39095/380/03.19 костюмы", "Мужская коллекция/Костюмы муж", "костюм")
        )


class SeasonTests(unittest.TestCase):
    def test_dates_vl(self):
        a, b = season_dates("VL", 2025)
        self.assertEqual(a.isoformat(), "2025-02-01")
        self.assertEqual(b.isoformat(), "2025-08-31")

    def test_marker(self):
        self.assertTrue(matches_season_marker("Куртка ВЛ2025 /03.25", "VL", 2025))
        self.assertTrue(matches_season_marker("Пальто ОЗ24", "OZ", 2024))
        self.assertFalse(matches_season_marker("Куртка ВЛ2024", "VL", 2025))


class BrandSalesSupplierTests(unittest.TestCase):
    def test_article_season(self):
        from app.services.warehouse_analytics.operations import article_collection_season, matches_season_marker

        self.assertEqual(article_collection_season("S-2472-00/B410/02.26 пиджак"), ("VL", 2026))
        self.assertEqual(article_collection_season("2890-00/В401/11.25"), ("OZ", 2025))
        self.assertTrue(matches_season_marker("S-2472-00/B410/02.26 пиджак", "VL", 2026))
        self.assertFalse(matches_season_marker("S-2472-00/B410/02.26 пиджак", "OZ", 2025))
        self.assertTrue(matches_season_marker("Куртка ВЛ2026", "VL", 2026))

    def test_brand_sales_uses_supplier_filter(self):
        client = MagicMock()
        client.href.side_effect = lambda e, i: f"https://api.moysklad.ru/api/remap/1.2/entity/{e}/{i}"

        def get_rows(path, params=None):
            params = params or {}
            if path == "/entity/counterparty":
                return (
                    [{"id": "85b76c4f-8e8b-11e9-9ff4-31500007fdb1", "name": "Roy Robson"}],
                    1,
                )
            if path == "/report/profit/byproduct":
                filt = str(params.get("filter") or "")
                self.assertIn("supplier=", filt)
                self.assertIn("85b76c4f-8e8b-11e9-9ff4-31500007fdb1", filt)
                return (
                    [
                        {
                            "name": "S-2472-00/B410/02.26 пиджак",
                            "article": "S-2472-00/B410/02.26",
                            "pathName": "Мужская коллекция/Пиджаки, жакеты, бомбер муж",
                            "sellQuantity": 5,
                            "sellSum": 16277915,  # kopecks
                            "sellCostSum": 5000000,
                            "profit": 11277915,
                        },
                        {
                            "name": "старый пуловер 10.23",
                            "article": "1870-91/А220/10.23",
                            "pathName": "Мужская коллекция/Трикотаж муж",
                            "sellQuantity": 1,
                            "sellSum": 795000,
                            "sellCostSum": 300000,
                            "profit": 495000,
                        },
                        {
                            "name": "16802-90/А401/02.26 поло",
                            "article": "16802-90/А401/02.26",
                            "pathName": "Мужская коллекция/Футболки, поло муж",
                            "sellQuantity": 4,
                            "sellSum": 4464360,
                            "sellCostSum": 1000000,
                            "profit": 3464360,
                        },
                    ],
                    3,
                )
            return ([], 0)

        client.get_rows.side_effect = get_rows
        out = run_operation(
            client,
            "brand_sales",
            {
                "brand": "Roy Robson",
                "season": "VL",
                "year": 2026,
                "date_from": "2026-01-01",
                "date_to": "2026-07-31",
                "store": "antrasha",
            },
            use_cache=False,
        )
        self.assertEqual(out["method"], "report/profit/byproduct+filter=supplier")
        self.assertEqual(out["matched_sales_rows"], 2)
        self.assertAlmostEqual(out["total_sell_sum"], 162779.15 + 44643.60, places=1)
        self.assertEqual(out["total_sell_quantity"], 9)
        cats = {c["category"]: c for c in out["by_category"]}
        self.assertIn("Пиджаки, жакеты, бомбер муж", cats)
        self.assertIn("Футболки, поло муж", cats)
        # OZ article excluded
        self.assertTrue(all("10.23" not in (i.get("article") or "") for i in out["top_items"]))

    def test_brand_key_and_gender(self):
        from app.services.warehouse_analytics.operations import _brand_key, _gender_from_path

        self.assertEqual(_brand_key("DUNO(муж)"), "DUNO")
        self.assertEqual(_brand_key("TREVI (жен)"), "TREVI")
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


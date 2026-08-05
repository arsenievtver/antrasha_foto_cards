"""Константы учёта ANTRASHA для semantic analytics."""

from __future__ import annotations

STORE_ANTRASHA_ID = "1d4d5f44-7bb1-11e9-9109-f8fc00054224"
STORE_STOCK_ID = "7321b022-99e3-11f0-0a80-0d050006f800"
RETAILSTORE_ANTRASHA_ID = "ec683f46-b383-11e9-9109-f8fc00111b52"
ORG_IP_BOGDANOVA_ID = "152bfbab-4d66-11ea-0a80-0029000fa8d8"

MS_API_BASE = "https://api.moysklad.ru/api/remap/1.2"

# Лимиты facts для writer (токены / шум).
MAX_SERIES_POINTS = 40
MAX_TOP_ROWS = 25
MAX_PRODUCTS_BRAND = 80
MAX_PURCHASE_LINES = 60
MAX_BRAND_SALES_ROWS = 1000
MAX_BRAND_SALES_PAGES = 5

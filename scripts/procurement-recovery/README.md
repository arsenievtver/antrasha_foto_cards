# Восстановление закупок (work / procurement)

Два источника на Mac:

| Источник | Путь | Суть |
|----------|------|------|
| Cursor | `~/Downloads/antrasha-procurement-recovery-2026-10-11` | Списки из истории MCP, **срез ~29.09.2026** (25 оплат) |
| Cloud | `~/Downloads/Резерв Антраша/1_PWA_из_базы_дашборда` | Кэш локального дашборда, **до 10.10.2026 22:16 UTC** (34 оплаты) |

Папки `2_*`, `3_*`, `4_*` в «Резерв Антраша» — черновики, логистика, sqlite дашборда; **в PWA (фото, пользователи, свайпы) не входят**.

## Объединение

```bash
python3 scripts/procurement-recovery/merge_sources.py
```

Результат: `scripts/procurement-recovery/merged/*.json` (не коммитить — в `.gitignore`).

Сводка объединения (12.10.2026):

- сезоны **3** (+ «Весна-лето 2026» из Cloud)
- бренды **22**, категории **21** (справочник), заказы **26** (~140 601 EUR)
- оплаты **34** (~72 258 EUR) — Cloud новее Cursor
- поставки **8** (объединены расхождения cursor/cloud)
- курсы **2**

## Импорт в прод

MCP `create_*` **не задаёт старые UUID** — оплаты и строки заказов развалятся. Нужен скрипт с сохранением id:

```bash
# на сервере (merged только на хосте — сначала docker cp, см. ниже)
docker cp scripts/procurement-recovery/merged "$(docker compose -f deploy/docker-compose.prod.yml --project-directory deploy ps -q backend | head -1)":/tmp/procurement-merged

docker compose -f deploy/docker-compose.prod.yml --project-directory deploy exec -T backend \
  sh -c 'cd /app && PYTHONPATH=/app python scripts/import_procurement_merged.py /tmp/procurement-merged --dry-run'

docker compose -f deploy/docker-compose.prod.yml --project-directory deploy exec -T backend \
  sh -c 'cd /app && PYTHONPATH=/app python scripts/import_procurement_merged.py /tmp/procurement-merged'

docker compose -f deploy/docker-compose.prod.yml --project-directory deploy exec -T backend \
  sh -c 'cd /app && PYTHONPATH=/app python scripts/patch_procurement_line_categories.py /tmp/procurement-merged --dry-run'

docker compose -f deploy/docker-compose.prod.yml --project-directory deploy exec -T backend \
  sh -c 'cd /app && PYTHONPATH=/app python scripts/patch_procurement_line_categories.py /tmp/procurement-merged'
```

Строки заказов: `category_id` маппится по **имени + полу** на категории текущей БД (uuid после миграции другие).

После импорта проверка: MCP `list_seasons`, `list_brand_orders`, `get_prepayment_overview`.

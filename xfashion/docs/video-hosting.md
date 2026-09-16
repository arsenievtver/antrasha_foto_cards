# Видео презентации Xfashion (РФ, без VPN)

Тяжёлый файл **не кладите в git** и не отдавайте напрямую с контейнера лендинга — первый экран будет тормозить.

## Рекомендуемая схема

1. Загрузите MP4 (H.264 + AAC, битрейт 4–8 Мбит/с) в **Yandex Object Storage** (бакет в `ru-central1`, публичный read на объект или CDN):
   - **Десктоп:** 1920×1080 (16:9), hero с `object-fit: cover`.
   - **Мобилка (рекомендуется):** отдельный **1080×1920 (9:16)** — тот же монтаж, но кадр с текстом/интерфейсом по центру; на телефоне снова full-bleed без обрезки боковин.
   - Пока нет 9:16 — на экранах ≤768px лендинг показывает **16:9 целиком** (`contain`, тёмные поля сверху/снизу), чтобы не резать боковой текст в ролике.
2. Подключите **CDN Yandex Cloud** к бакету — трафик пойдёт из РФ с кешированием.
3. В прод-сборке задайте URL:
   - `deploy/env/.env.prod`: `XFASHION_VIDEO_URL=https://…`, опционально `XFASHION_VIDEO_MOBILE_URL=https://…`
   - Docker build args → `VITE_XFASHION_VIDEO_URL` / `VITE_XFASHION_VIDEO_MOBILE_URL` (см. `deploy/docker-compose.prod.yml`).
4. На `<video>` уже стоит `preload="metadata"` — полный файл не тянется до Play.

## Альтернативы

- **VK Video** / **Rutube** — embed iframe, если не хотите свой CDN (хуже для «видео в центре», но нулевая нагрузка на VM).
- Прокси через nginx `/media/xfashion/promo.mp4` с `mp4;` и `Accept-Ranges` — только если файл лежит на VM/бакете рядом с antrasha.

## Текущий файл (prod + dev)

https://storage.yandexcloud.net/files-for-sites/Antrasha_AI_fashion_web_1080p.mp4

- Локально: `xfashion/.env.development` (Vite подхватывает сам).
- Прод-сборка: `XFASHION_VIDEO_URL` в `deploy/env/.env.prod`.
- В коде есть тот же URL как fallback, если переменная не задана при `build`.

## Локальная разработка

Другой URL — `xfashion/.env.local` (не в git).

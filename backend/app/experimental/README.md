# Experimental integrations

Экспериментальный код, который можно удалить без ломки основного приложения.

## Ximilar (`experimental/ximilar/`)

Автоподбор тегов через API Ximilar Fashion Tagging.

**Удаление эксперимента:**

1. Удалить каталог `backend/app/experimental/ximilar/` и правку `include_router` в `app/routers/admin.py`.
2. Удалить из `app/config.py` поле `api_ximilar` и блок из startup log в `main.py` (если добавлен).
3. В админке: `admin/src/api.js` — функция `suggestXimilarTags`; `admin/src/pages/Photos.jsx` — кнопка «AI».
4. Убрать `API_XIMILAR` из `.env`.

**Требования:** публичный URL картинки (Object Storage по HTTPS), иначе Ximilar не скачает файл.

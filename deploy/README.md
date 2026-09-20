# Production deploy on Yandex Cloud VM

## 1) Prepare server

1. Create Ubuntu 22.04 VM in Yandex Cloud.
2. Point DNS records:
   - `new.antrasha.ru` -> VM public IP
   - `admin.antrasha.ru` -> VM public IP
3. SSH to VM and install base dependencies:

```bash
sudo bash deploy/scripts/install-server.sh
```

## 2) Put project on server

```bash
sudo mkdir -p /opt/antrasha_tinder
sudo chown -R "$USER":"$USER" /opt/antrasha_tinder
cd /opt/antrasha_tinder
git clone <YOUR_REPO_URL> .
```

## 3) Configure production env

```bash
cp deploy/env/.env.prod.example deploy/env/.env.prod
cp deploy/env/.env.backend.prod.example deploy/env/.env.backend.prod
cp deploy/env/.env.postgres.prod.example deploy/env/.env.postgres.prod
```

Fill the files:
- `deploy/env/.env.prod`: `APP_DOMAIN`, `ADMIN_DOMAIN`
- `deploy/env/.env.postgres.prod`: DB credentials
- `deploy/env/.env.backend.prod`: `DATABASE_URL`, `JWT_SECRET`, CORS, admin superuser

## 4) First deploy

```bash
bash deploy/scripts/first-deploy.sh
```

Check:

```bash
curl -fsS http://127.0.0.1/health
docker compose -f deploy/docker-compose.prod.yml --project-directory deploy ps
```

## 5a) Xfashion landing only

Лендинг — отдельный контейнер `xfashion`, деплой без пересборки всего антраша:

```bash
bash deploy/scripts/update-xfashion.sh
```

После изменений API (`/public/xfashion/*`, миграции):

```bash
WITH_BACKEND=1 bash deploy/scripts/update-xfashion.sh
```

Перед первым `update.sh` с xfashion добавь в `deploy/env/.env.prod` строку `XFASHION_DOMAIN=xfashion.pro` — без неё nginx не стартует (весь сайт, не только лендинг).

Первый TLS для `XFASHION_DOMAIN` (когда DNS уже на VM):

```bash
bash deploy/scripts/tls-add-xfashion.sh
```

Пока не выпущен Let's Encrypt для xfashion, nginx может отдавать **self-signed placeholder** — сайт по `https://` открывается только после «продолжить» или не открывается вовсе. Проверка:

```bash
bash deploy/scripts/check-xfashion-tls.sh
```

В `deploy/env/.env.prod`: `XFASHION_PUBLIC_URL=https://xfashion.pro` (canonical/sitemap в сборке лендинга).

В `deploy/env/.env.prod`: `XFASHION_DOMAIN`, опционально `XFASHION_VIDEO_URL` (CDN).  
В `deploy/env/.env.backend.prod`: `PUBLIC_XFASHION_URL=https://xfashion.pro`, CORS с xfashion.pro.  
Рекламные ссылки Xfashion — в админке: **Xfashion — ссылки**.

## 5) Updates (one command)

На сервере из каталога репозитория (например `/opt/antrasha_tinder`):

```bash
bash deploy/scripts/update.sh
```

Или то же самое через обёртку (удобно запомнить одно имя):

```bash
bash deploy/scripts/server-pull-deploy.sh
```

Оба варианта делают:
- `git pull --ff-only`
- сборка образов `backend` / `frontend` / `admin`
- подъём Postgres, миграции Alembic **до** перезапуска API
- материализацию активного nginx-шаблона из источника (TLS — если есть Let's Encrypt сертификат для `APP_DOMAIN`, иначе HTTP) с `force-recreate nginx`
- `docker compose up -d` всего стека
- проверка `/health`

### После изменений кода локально (рабочий цикл)

1. Локально: закоммить и **запушить** в `main` (или ту ветку, с которой клонируешь прод).
2. На сервере по SSH:

```bash
cd /opt/antrasha_tinder
bash deploy/scripts/server-pull-deploy.sh
```

3. Если в коммите менялся каталог тегов [`backend/app/tag_catalog_seed.py`](../backend/app/tag_catalog_seed.py), один раз после деплоя добавь сид:

```bash
bash deploy/scripts/server-pull-deploy.sh --with-tags
```

Это то же самое, что `TAG_CATALOG_SEED=1 bash deploy/scripts/update.sh`.

**Про сид тегов:** идемпотентно — новые теги добавятся, пары группа+имя не дублируются. Повторный seed **обновляет поля групп** (title, min/max, сортировки) для совпадающих `slug` из файла; правки **метаданных групп** только в админке на сервере могут быть перезаписаны при следующем сиде. Сами уже существующие теги с тем же именем сид не пересоздаёт.

Ручной сид без полного деплоя:

```bash
docker compose -f deploy/docker-compose.prod.yml --project-directory deploy exec -T backend \
  python -m app.tag_catalog_seed
```

## 6) Backups and restore

Create backup:

```bash
bash deploy/scripts/backup-db.sh
```

Restore backup:

```bash
bash deploy/scripts/restore-db.sh /absolute/path/to/postgres_dump.sql.gz
```

## 7) Rollback

Rollback to previous commit:

```bash
bash deploy/scripts/rollback.sh HEAD~1
```

Or rollback to explicit ref/tag:

```bash
bash deploy/scripts/rollback.sh <commit_or_tag>
```

## 8) TLS (HTTPS with Let's Encrypt)

Set in `deploy/env/.env.prod`:
- `APP_DOMAIN`
- `ADMIN_DOMAIN`
- `LETSENCRYPT_EMAIL`

Then enable TLS:

```bash
bash deploy/scripts/tls-enable.sh
```

This script:
- requests certificates via `certbot` (webroot challenge),
- copies the TLS template [`deploy/nginx/default.tls.conf.template`](nginx/default.tls.conf.template) over `deploy/nginx/templates/default.conf.template` and recreates nginx.

После первого включения TLS никаких ручных шагов не нужно: дальнейший `update.sh` сам обнаружит выпущенный сертификат и каждый деплой будет перекладывать актуальный TLS-источник в `templates/default.conf.template`.

**Important:** the official `nginx` Docker image turns **every** file matching `*.template` under `deploy/nginx/templates/` into a separate `.conf`. Do not place the TLS template there until certificates exist — it would make nginx load broken `443` blocks and crash-loop. The TLS file lives **next to** `templates/`, not inside it.

> Активный шаблон `deploy/nginx/templates/default.conf.template` **не отслеживается git'ом** (см. `.gitignore`) — это сгенерированный артефакт. Источники истины — `deploy/nginx/default.http.conf.template` и `deploy/nginx/default.tls.conf.template`. При правках nginx-конфига меняй именно их.

Check:

```bash
curl -I "https://$(awk -F= '/^APP_DOMAIN=/{print $2}' deploy/env/.env.prod)"
curl -I "https://$(awk -F= '/^ADMIN_DOMAIN=/{print $2}' deploy/env/.env.prod)"
```

Renew manually:

```bash
bash deploy/scripts/tls-renew.sh
```

Add auto-renew via cron (daily at 03:17):

```bash
(crontab -l 2>/dev/null; echo '17 3 * * * cd /opt/antrasha_tinder && bash deploy/scripts/tls-renew.sh >> /var/log/antrasha-tls-renew.log 2>&1') | crontab -
```

## Vector taste (pgvector + embedding worker)

Postgres image: `pgvector/pgvector:pg16` (extension `vector` создаётся миграцией `046_vector_taste`).

1. Deploy backend as usual (`alembic upgrade head`).
2. Backfill embeddings (один из вариантов):
   - **Отдельная машина / Mac:** `pip install -r backend/requirements-embeddings.txt`, `DATABASE_URL=... python -m jobs.photo_embedding_worker` (остановить когда очередь пуста).
   - **На VM с профилем:** `docker compose -f deploy/docker-compose.prod.yml --profile embeddings up -d photo-embedding-worker`
3. В админке **Feed settings** переключить `feed_ranking_mode`: `tags` → `hybrid` → `vectors` после того как большинство активных фото имеют embedding.

**RAM на VM 2 GB:** API + Postgres + nginx умещаются; **воркер CLIP/fastembed на том же 2 GB не рекомендуется** (пик ~1–1.5 GB на инференс). Либо апгрейд до **4 GB**, либо backfill с ноутбука по `DATABASE_URL`, либо вынести worker на вторую маленькую VM.

## Сборка упала на `frontend build … npm run build`

На машине **2 GB** частая причина — **не ошибка кода**, а **OOM**: `update.sh` раньше собирал `frontend admin work xfashion` параллельно с backend. Сейчас образы собираются **по очереди**.

На сервере посмотреть реальный лог (не только красную строку в Docker Desktop):

```bash
cd /opt/antrasha_tinder
docker compose -f deploy/docker-compose.prod.yml build frontend 2>&1 | tee /tmp/frontend-build.log
tail -80 /tmp/frontend-build.log
echo "exit=$?"
dmesg 2>/dev/null | tail -5 | rg -i 'kill|oom' || true
```

- **exit=137** или **Killed** в логе → не хватило RAM: включить **swap 2G** или апгрейд VM, собирать по одному сервису.
- Текст ошибки **Vite / Rollup** → прислать последние 30 строк лога (это уже код/зависимости).

После успешной сборки frontend не забудьте миграции (`046`–`048`) и образ Postgres **`pgvector/pgvector:pg16`** — без них backend может падать уже после build.

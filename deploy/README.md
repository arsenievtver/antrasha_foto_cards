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

**Important:** the official `nginx` Docker image turns **every** file matching `*.template` under `deploy/nginx/templates/` into a separate `.conf`. Do not place the TLS template there until certificates exist — it would make nginx load broken `443` blocks and crash-loop. The TLS file lives **next to** `templates/`, not inside it.

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

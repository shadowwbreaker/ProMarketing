# Бета на Vercel + Neon + Upstash + Cloudflare R2

Ветка `beta`. Оплата имитируется (`PAYMENT_PROVIDER=mock`), остальное работает по-настоящему.

## Как устроено

```
браузер → pm-web.vercel.app (Next.js)
            └─ /api/v1/*  →  pm-api.vercel.app (Django, serverless-функция)
                               ├─ Neon (PostgreSQL)
                               ├─ Upstash (Redis: кэш, лимиты запросов)
                               └─ Cloudflare R2 (файлы чата, аватары)
GitHub Actions: миграции при push в beta; таймеры каждые 15 минут → /api/v1/ops/tick
```

Сайт и API для браузера на одном домене (Next.js проксирует `/api/v1`), поэтому cookie входа и CSRF работают без настроек доменов.

## 1. Cloudflare R2 (файлы)

1. Cloudflare → R2 Object Storage → **Create bucket** → имя `promarketing-beta`, регион Automatic.
2. R2 → **Manage API tokens** → **Create API token** → права *Object Read & Write*, только этот bucket.
3. Сохраните: **Access Key ID**, **Secret Access Key**, и **Account ID** (виден справа на странице R2).

## 2. Vercel: проект API (backend)

1. Vercel → **Add New → Project** → репозиторий `ProMarketing`.
2. **Root Directory** → `backend`. Framework Preset → *Other*. Имя проекта, например `pm-api`.
3. До нажатия Deploy раскройте **Environment Variables** и добавьте (таблица ниже). Deploy.
4. Settings → **Git → Production Branch** → `beta`.
5. Вкладка **Storage** → **Create Database** → **Neon** (регион Frankfurt) → Connect к `pm-api`. Появятся `DATABASE_URL` и `DATABASE_URL_UNPOOLED`.
6. Снова **Storage** → **Upstash for Redis** (регион Frankfurt) → Connect к `pm-api`. Появятся `KV_URL` / `REDIS_URL`.
7. Deployments → последний → **Redeploy** (чтобы подхватились переменные баз).

| Переменная | Значение |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.vercel` |
| `DJANGO_SECRET_KEY` | случайная строка ≥ 50 символов (команда ниже) |
| `FIELD_ENCRYPTION_KEY` | ключ Fernet (команда ниже) |
| `CRON_SECRET` | случайная строка (команда ниже) |
| `FRONTEND_URL` | `https://pm-web.vercel.app` (адрес сайта из шага 3) |
| `CSRF_TRUSTED_ORIGINS` | `https://pm-web.vercel.app` |
| `CORS_ALLOWED_ORIGINS` | `https://pm-web.vercel.app` |
| `DJANGO_ALLOWED_HOSTS` | `pm-api.vercel.app` (адрес этого проекта) |
| `S3_BUCKET` | `promarketing-beta` |
| `S3_ENDPOINT_URL` | `https://<Account ID>.r2.cloudflarestorage.com` |
| `S3_REGION` | `auto` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | ключи из шага 1 |
| `YOUTUBE_API_KEY` | ваш ключ YouTube Data API |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | ключи TikTok (если нет — TikTok только вручную) |
| `DEV_AUTO_VERIFY_EMAIL` | `true` (почта подтверждается сразу; позже — SMTP) |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` |

Генерация секретов (на своём ПК, в папке backend с установленным Python):

```bash
python -c "import secrets;print(secrets.token_urlsafe(64))"     # DJANGO_SECRET_KEY
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"  # FIELD_ENCRYPTION_KEY
python -c "import secrets;print(secrets.token_urlsafe(32))"     # CRON_SECRET
```

`FIELD_ENCRYPTION_KEY` после первого запуска не меняйте — им зашифрованы токены каналов.

## 3. Vercel: проект сайта (frontend)

1. **Add New → Project** → тот же репозиторий → **Root Directory** `frontend`, Framework *Next.js*, имя `pm-web`.
2. Переменные:

| Переменная | Значение |
|---|---|
| `BACKEND_ORIGIN` | `https://pm-api.vercel.app` |
| `API_INTERNAL_URL` | `https://pm-api.vercel.app` |
| `NEXT_PUBLIC_API_URL` | `/` (запросы идут на тот же домен) |

3. Deploy, затем Settings → Git → Production Branch → `beta`.

Если адреса проектов получились другими — поправьте `FRONTEND_URL`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `DJANGO_ALLOWED_HOSTS`, `BACKEND_ORIGIN` и сделайте Redeploy обоих.

## 4. GitHub: миграции и таймеры

Репозиторий → Settings → **Secrets and variables → Actions → New repository secret**:

| Secret | Значение |
|---|---|
| `DATABASE_URL_UNPOOLED` | скопировать из Vercel → pm-api → Settings → Environment Variables |
| `CRON_SECRET` | то же, что в pm-api |
| `BETA_SITE_URL` | `https://pm-api.vercel.app` |

Затем Actions → **beta-ops** → **Run workflow** (ветка `beta`) — создаст таблицы в Neon. Дальше миграции идут сами при каждом push в `beta`, таймеры (автозавершение заказов, выплаты через 48 ч, обновление статистики) — каждые 15 минут.

## 5. Первый администратор

На своём ПК в `backend` (с `.venv`):

```bash
set DATABASE_URL=<DATABASE_URL_UNPOOLED из Vercel>
set DJANGO_SETTINGS_MODULE=config.settings.ops
python manage.py createsuperuser
```

(в PowerShell: `$env:DATABASE_URL="..."`).

## 6. Проверка

- `https://pm-api.vercel.app/api/v1/health/ready` → `{"database":"ok","cache":"ok"}`
- `https://pm-web.vercel.app` → жёлтая плашка «Бета-версия», регистрация, добавление канала YouTube по ссылке, покупка → «Оплата подтверждена», заказ виден в чате.

## 7. TikTok

В TikTok for Developers → приложение → Login Kit → **Redirect URI**: `https://pm-web.vercel.app/account/accounts/oauth/tiktok`. Домен `*.vercel.app` нужно подтвердить в разделе URL properties, если TikTok попросит.

## Ограничения бесплатной беты

- Vercel Hobby — только некоммерческое использование; для реальных продаж — тариф Pro или свой сервер (`docs/DEPLOYMENT.md`).
- Данные хранятся во Франкфурте — для боевого запуска в РФ нужен хостинг в РФ (152-ФЗ).
- Neon засыпает без запросов — первый заход после паузы медленнее на 1–3 секунды.
- Лимиты: Neon 0,5 ГБ, Upstash 500 тыс. команд/мес, R2 10 ГБ, функция Vercel до 60 с.

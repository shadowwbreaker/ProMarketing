# Бета на Vercel + Neon + Upstash

Ветка `beta`. Оплата имитируется (`PAYMENT_PROVIDER=mock`), остальное работает по-настоящему.

## Публичный домен и проверки после смены адреса

- Основной адрес сайта — `https://www.yourvideoteam.agency`. Домен без `www` перенаправляет на основной, старый `https://promarketing-beta-web.vercel.app` остаётся доступен. Браузер обращается к `/api/v1` на адресе сайта; Next.js пересылает запросы в `https://promarketing-beta-api.vercel.app`.
- В Production проекта `promarketing-beta-api` задайте `FRONTEND_URL=https://www.yourvideoteam.agency`. Этот адрес используется в письмах подтверждения и восстановления, уведомлениях по заказам и TikTok OAuth. В `CSRF_TRUSTED_ORIGINS` и `CORS_ALLOWED_ORIGINS` оставьте `https://www.yourvideoteam.agency,https://promarketing-beta-web.vercel.app`. Значения должны быть одной строкой, без завершающих слэшей. После сохранения заново разверните API. Сохранение без нового деплоя не меняет работающую функцию.
- Проверьте вход с основного домена. Запрос входа с CSRF-cookie и заголовком проходит проверку источника, пустая форма получает `400 validation_error`. Запрос без токена получает `403`. Прямой API для разрешённого Origin возвращает соответствующий `Access-Control-Allow-Origin`.
- В TikTok Developer Portal добавьте точный Redirect URI `https://www.yourvideoteam.agency/account/accounts/oauth/tiktok` для среды, ключи которой установлены в API. После сохранения проверьте согласие и возврат на этот же домен. Переход между доменами не переносит cookie входа. Старый Redirect URI ниже оставлен для истории перехода.
- Для TikTok используются `https://www.yourvideoteam.agency/`, `https://www.yourvideoteam.agency/privacy/` и `https://www.yourvideoteam.agency/terms/`. Файлы подтверждения для каждого префикса лежат соответственно в `frontend/public/`, `frontend/public/privacy/` и `frontend/public/terms/`. Успешная выдача файла подтверждает доступность пути, а статус проверки приложения смотрите в TikTok Developer Portal.

## Как устроено

```
браузер → pm-web.vercel.app (Next.js)
            └─ /api/v1/*  →  pm-api.vercel.app (Django, serverless-функция)
                               ├─ Neon (PostgreSQL: данные, файлы чата, аватары)
                               └─ Upstash (Redis: кэш, лимиты запросов)
GitHub Actions: миграции при push в beta; таймеры каждые 15 минут → /api/v1/ops/tick
```

Сайт и API для браузера на одном домене, Next.js проксирует `/api/v1`. Cookie привязаны к этому домену. Django при этом должен доверять домену сайта в `CSRF_TRUSTED_ORIGINS`, поскольку получает запрос через прокси.

На Vercel бета принимает аватары и вложения до 4 МБ с учётом ограничения на размер HTTP-запроса. Каждая операция тестовой оплаты хранится в PostgreSQL, чтобы подтверждение, возврат и выплата работали между разными экземплярами функции.

Файлы беты входят в лимит хранилища проекта Neon. Настройки Vercel включают хранение в PostgreSQL по умолчанию.

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
| `YOUTUBE_API_KEY` | ваш ключ YouTube Data API |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | ключи TikTok (если нет — TikTok только вручную) |
| `DEV_AUTO_VERIFY_EMAIL` | `false` |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP-сервер и порт, для Gmail — `smtp.gmail.com`, `587` |
| `EMAIL_HOST_USER`, `DEFAULT_FROM_EMAIL` | аккаунт отправителя и адрес From |
| `EMAIL_HOST_PASSWORD` | секрет SMTP. Для Gmail — [пароль приложения Google](https://support.google.com/accounts/answer/185833?hl=ru) |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | для порта 587 — `true` и `false` соответственно |

Генерация секретов (на своём ПК, в папке backend с установленным Python):

```bash
python -c "import secrets;print(secrets.token_urlsafe(64))"     # DJANGO_SECRET_KEY
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"  # FIELD_ENCRYPTION_KEY
python -c "import secrets;print(secrets.token_urlsafe(32))"     # CRON_SECRET
```

`FIELD_ENCRYPTION_KEY` после первого запуска не меняйте — им зашифрованы токены каналов.

В публичной бете статус подтверждённого адреса выдаётся только после проверки ссылки. При недоступном SMTP пользователь может войти и открыть каталог, а оформление заказа и публикация предложения требуют подтверждения. Кнопка повторной отправки возвращает понятную ошибку, пока провайдер недоступен. После добавления SMTP-переменных разверните API заново и проверьте регистрацию и получение письма на подконтрольный адрес. [SMTP на Vercel](https://vercel.com/kb/guide/serverless-functions-and-smtp)

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
- `https://promarketing-beta-web.vercel.app` → регистрация → письмо с подтверждением → каталог → покупка → «Оплата подтверждена», заказ виден в чате.
- Администратор входит через сайт, настраивает TOTP в профиле и открывает `/staff`. `/django-admin/` на публичном API возвращает 404.
- При обновлении сначала дождитесь успешной миграции в Actions, затем разверните фронтенд и API из этого же коммита `beta`. Проверьте HTTP 200 у readiness, загрузку карточки каталога и отказ при POST входа без CSRF.
- `old-main` сохраняет исходный SHA `00da2d5477a4d891feda71e04d6c90e3f833df3d` для просмотра предыдущей версии. Для отката публичной беты используйте подходящий деплой Vercel с учётом миграций. Историческая ветка сохраняет код, текущее содержимое Neon в неё не входит.

## 7. TikTok

В TikTok for Developers → приложение → Login Kit → **Redirect URI**: `https://promarketing-beta-web.vercel.app/account/accounts/oauth/tiktok`. Нужны Login Kit, Display API и scopes `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`. В Sandbox владелец тестового TikTok-аккаунта должен быть добавлен в Target users.

Ключи добавляются как Secret для окружения Production в проекте `promarketing-beta-api`: `YOUTUBE_API_KEY`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`. После сохранения нужен повторный деплой API. Для YouTube владелец видит среднее по выборке из последних доступных коротких роликов (до 15), а публичный показ производной метрики требует одобрения YouTube (D-016).

## 8. Вложения и защита от флуда

- Без ClamAV Vercel принимает статичные PNG, JPEG, GIF и WebP. Бэкенд декодирует и пересобирает их и удаляет вложенные метаданные. Для PDF и видео можно приложить ссылку в споре. Вложения, созданные до исправления, остаются в хранилище и выдаются только после проверки командой `rescan_attachments` с доверенным сканером.
- Базовая защита Vercel DDoS Mitigation включена. Настройки правила уровня Vercel WAF для каждого проекта находятся в [отчёте о выпуске](TEST_REPORT_2026-11-15.md). Проверяйте статусы и окно частоты для публичного фронтенда и прямого API отдельно. Не направляйте нагрузочный тест на публичные адреса.

Дополнение к защите: в каждом проекте отдельно проверьте активное правило для префикса `/api/v1/`, HTTP 429 и окно 60 секунд на IP. Подготовленные пороги — 240 запросов для сайта и 1200 для прямого API. `/health/ready` проверяет PostgreSQL и Redis не чаще раза в пять секунд на процесс, а `/health/live` не проверяет зависимости. Для проверки рабочего сайта достаточно обычных запросов и инспекции активной конфигурации.

## Ограничения бесплатной беты

- Vercel Hobby — только некоммерческое использование; для реальных продаж — тариф Pro или свой сервер (`docs/DEPLOYMENT.md`).
- Данные хранятся во Франкфурте — для боевого запуска в РФ нужен хостинг в РФ (152-ФЗ).
- Neon засыпает без запросов — первый заход после паузы медленнее на 1–3 секунды.
- Лимиты: Neon 0,5 ГБ, Upstash 500 тыс. команд/мес, R2 10 ГБ, функция Vercel до 60 с.

## Актуализация · 18 ноября 2026

Первый владелец регистрируется как maxshishkin07@gmail.com, подтверждает email и настраивает TOTP. Пароль заранее не задан. ENABLE_TEST_FIXTURES отсутствует/false. До нового API обязательны support.0004 и accounts.0007: backup main → beta → успешный beta-ops migrate → API/web одного коммита → проверка → main. old-main сохраняется. [Протокол](RELEASE_2026-11-18.md).

Перед переносом этого исправления исходный `main` с SHA `7d4f74beecb8161275d06b87889031b29cf16808` сохранён в `old-main-7d4f74b`. Более ранняя резервная ветка `old-main` сохранена отдельно.

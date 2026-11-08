# DEPLOYMENT — подготовка к запуску и выпуск

Статус: Phase 15 подготовлена (2026-11-07). **Production deployment запрещён без отдельного разрешения владельца проекта** (roadmap 2.4). Этот документ — инструкция на момент, когда разрешение будет получено.

## 1. Блокеры запуска (не технические)

| ID | Что нужно | Почему блокирует |
|---|---|---|
| Q-03 | Договор с платёжным провайдером (ЮKassa «Безопасная сделка» или Т-Бизнес «Мультирасчёты») и адаптер к нему | Без провайдера деньги не принимаются; mock запрещён в production (приложение не стартует) |
| Q-09 | Юрлицо платформы, статус продавцов (физлица / самозанятые / ИП) | Договор с провайдером, налоги, выплаты |
| EXT-1 | Одобрение TikTok (Login Kit + Display API), ключ YouTube Data API, заявка на derived metrics (D-016) | Без ключей статистика доступна только вручную (`MANUAL`) |
| LEGAL | Юрист: оферта, политика конфиденциальности, правила (черновики — `docs/legal/`), маркировка рекламы (ОРД, erid), реестр блогеров РКН, рекламный сбор, 152-ФЗ (локализация ПДн в РФ) | Обязательные требования для рынка РФ (D-013) |

## 2. Инфраструктура

| Компонент | Файл | Примечание |
|---|---|---|
| Backend (gunicorn, non-root) | `backend/Dockerfile.prod` | `DJANGO_SETTINGS_MODULE=config.settings.prod` |
| Frontend (Next.js standalone, non-root) | `frontend/Dockerfile.prod` | `NEXT_PUBLIC_API_URL` передаётся при сборке |
| Стек | `infra/docker-compose.prod.yml` | db, redis, backend, migrate, worker, beat, frontend, caddy |
| HTTPS | `infra/Caddyfile` | автоматические сертификаты Let's Encrypt |
| Бэкапы | `infra/scripts/backup.sh`, `restore-check.sh` | проверено 2026-11-07 на тестовых данных |

Хостинг: для 152-ФЗ персональные данные граждан РФ хранятся на серверах в РФ (Yandex Cloud, Selectel, VK Cloud и т. п.). Хранилище файлов — S3-совместимое в РФ.

## 3. Переменные окружения production

Обязательные (приложение не стартует без них): `DJANGO_SECRET_KEY` (≥ 40 символов), `FIELD_ENCRYPTION_KEY` (Fernet), `DATABASE_URL`, `REDIS_URL`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `S3_BUCKET` (+ `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`), `EMAIL_BACKEND` (SMTP) и `EMAIL_HOST*`, `PAYMENT_PROVIDER` ≠ `mock`, `SOCIAL_PROVIDER_MODE=official`.

Рекомендуемые: `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN` (например `.promarketing.ru`, если API на поддомене), `SECURE_HSTS_PRELOAD=true` после подготовки домена, `STAFF_2FA_REQUIRED=true` (по умолчанию в prod), `GUNICORN_WORKERS`.

Секреты хранятся вне репозитория (секрет-менеджер облака или `.env.prod` с правами 600 на сервере). `.env*` в `.gitignore`.

## 4. Порядок выпуска

1. Резервная копия БД: `infra/scripts/backup.sh` → проверить `restore-check.sh` на свежем дампе.
2. Тег релиза в git (`vYYYY.MM.DD-N`), CI зелёный.
3. Сборка образов: `docker compose -f infra/docker-compose.prod.yml --env-file .env.prod build`.
4. Проверка конфигурации: `docker compose ... run --rm backend python manage.py check --deploy` (допустимо только предупреждение о HSTS preload).
5. Миграции: `docker compose ... run --rm migrate`. Миграции проекта обратимы, кроме триггеров append-only (откат удаляет их — делать только при откате всей версии).
6. Запуск: `docker compose ... up -d`.
7. Проверка: `GET https://API/api/v1/health/ready` → `200 {"database":"ok","cache":"ok"}`; вход сотрудника с 2FA; открыть каталог; `GET /api/v1/staff/audit/verify` → `ok: true`.
8. Наблюдение 30 минут: логи (`docker compose logs -f backend worker`), ошибки 5xx, очередь Celery.

## 5. План отката

| Ситуация | Действие |
|---|---|
| Ошибка в коде без изменений схемы | Вернуть предыдущий тег образов, `up -d` |
| Ошибка после миграции, данные не повреждены | Вернуть образы и `python manage.py migrate <app> <предыдущая_миграция>` по списку миграций релиза |
| Повреждение данных | Остановить запись (`docker compose stop backend worker beat`), восстановить из бэкапа, сверить платежи с провайдером по журналу `FinancialLedgerEntry` и выгрузке провайдера |
| Сбой провайдера / webhook | Платежи остаются `pending`, события сохраняются; повторная обработка — сверкой статуса (`get_payment_status`) |

После отката: запись в `MASTER_ROADMAP.md` (что, когда, почему) и разбор причины.

## 6. Мониторинг и логи

- Health: `/api/v1/health/live` (процесс жив), `/api/v1/health/ready` (БД и Redis) — для балансировщика и внешнего мониторинга (UptimeRobot / Яндекс Мониторинг).
- Логи: JSON в stdout с `request_id`, секреты маскируются; сбор — средствами хостинга.
- Что отслеживать: 5xx, время ответа, длина очереди Celery, `PaymentWebhookEvent.processing_error`, операции `pending_reconciliation`, спорные заказы без ответа, проверка целостности аудита.

## 7. Чек-лист roadmap Phase 15

См. статусы в `MASTER_ROADMAP.md`, раздел PHASE 15.

## 8. Защита от DDoS и флуда

- **До сервера (обязательно для production):** DDoS-Guard / Qrator / StormWall или защита облака (Yandex Cloud DDoS Protection). Приложение не способно отсечь распределённую атаку само.
- **Caddy:** таймауты чтения заголовков и тела (slowloris), лимит размера заголовков и тела запроса (`infra/Caddyfile`). Для лимитов на уровне прокси можно собрать Caddy с модулем `caddy-ratelimit`.
- **Приложение:** лимит на IP для гостей (`THROTTLE_ANON`, по умолчанию 300/мин) и на пользователя (`THROTTLE_USER`, 1200/мин), строгие лимиты входа, сообщений, загрузок. Счётчики общие для всех воркеров (Redis).
- **`NUM_PROXIES`** = число прокси перед приложением (1 — только Caddy; 2 — если перед Caddy есть ещё DDoS-защита/балансировщик). От этого зависит, увидит ли приложение настоящий IP посетителя.
- Результаты проверки — `docs/TEST_REPORT_2026-11-09.md`.

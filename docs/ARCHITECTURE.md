# ARCHITECTURE

Статус: предложение (Phase 0, 2026-11-07). Стек ждёт подтверждения (DECISIONS D-001).

## 1. Обзор

Модульный монолит: один backend (Django + DRF), один frontend (Next.js), PostgreSQL, Redis, воркер Celery, S3-совместимое хранилище файлов.

```
Browser ── Next.js (SSR/CSR) ──HTTPS/JSON──► Django REST API ──► PostgreSQL
                                                │   │
                                                │   └──► S3 / MinIO (доказательства, вложения)
                                                ▼
                                    Redis ◄── Celery worker ──► Social APIs (только по действию пользователя)
                                                            └──► Payment provider (через адаптер)
Payment provider ──webhook──► Django /api/payments/webhooks/<provider>/
```

## 2. Структура репозитория (целевая)

```
/
├─ MASTER_ROADMAP.md
├─ docs/
├─ backend/
│  ├─ config/             # settings (base/dev/test/prod), urls, celery
│  ├─ common/             # ошибки, валидация, пагинация, деньги, идемпотентность
│  ├─ accounts/           # пользователи, профили, роли, сессии
│  ├─ social_data/        # провайдеры статистики (см. SOCIAL_DATA.md)
│  ├─ catalog/            # SocialAccount-предложения, сетки, поиск
│  ├─ orders/             # заказы, позиции, машина состояний, условия
│  ├─ payments/           # адаптеры, webhook, журнал
│  ├─ chats/  notifications/  support/  reviews/  audit/  staff/
│  └─ tests/
├─ frontend/
│  ├─ app/  components/  lib/api/  styles/  tests/
├─ infra/
│  └─ docker-compose.yml
└─ .env.example           # без секретов; .env не создаётся и не изменяется Claude
```

## 3. Слои backend

- **API** (views/serializers): аутентификация, права, валидация входа, формат ответа.
- **Сервисы** (`services.py` модуля): вся бизнес-логика и переходы состояний, транзакции.
- **Модели**: данные и ограничения целостности. Без бизнес-логики переходов.
- **Адаптеры**: внешние системы (соцсети, платежи, хранилище, почта) — за интерфейсами, подменяются в тестах.

Правило: модуль не изменяет модели другого модуля напрямую, только через его сервис.

## 4. Машины состояний

Заказ (позиция заказа), спор, платёж, возврат, выплата — отдельные машины состояний. Таблица допустимых переходов в коде; каждый переход пишет `OrderEvent`/`AuditLog` в той же транзакции.

Статус заказа выводится из статусов позиций (например, «частично возвращён»), чтобы сетки работали без особых случаев.

## 5. Фоновые задачи

См. DECISIONS D-004. Celery beat используется только для внутренних таймеров (дедлайны) и задач удаления данных по политикам платформ. Ни одна периодическая задача не обращается к соцсетям.

## 6. Ошибки и логирование

- Единый формат ошибки API: `{ "error": { "code", "message", "details", "request_id" } }`.
- Структурированные JSON-логи, `request_id` сквозной; секреты и токены маскируются.
- Health-эндпоинты: `/api/health/live`, `/api/health/ready` (БД, Redis).

## 7. Окружения

`dev` (Docker Compose, mock-провайдеры), `test` (CI, mock), `staging` (тестовые ключи провайдеров), `production` (запрещён без разрешения). Конфигурация — переменные окружения; шаблон — `.env.example`.

## 8. Внешние сервисы

| Сервис | Назначение | Когда нужен |
|---|---|---|
| TikTok for Developers (Login Kit, Display API) | Статистика TikTok | Phase 3; заявку подать заранее |
| Meta for Developers (Instagram Platform) | Статистика Instagram | Phase 3; зависит от Q-01 |
| Google Cloud (YouTube Data API v3) | Статистика YouTube | Phase 3; derived metrics — заявка |
| Платёжный провайдер | Платежи, escrow, выплаты | Phase 7 |
| SMTP/транзакционная почта | Подтверждение email, уведомления | Phase 2 |
| S3-совместимое хранилище | Файлы доказательств | Phase 6/8 |
| ОРД (оператор рекламных данных) | Маркировка рекламы, если рынок РФ | До запуска; решение Q-01 |

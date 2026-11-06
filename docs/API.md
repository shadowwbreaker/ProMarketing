# API

Статус: соглашения (Phase 0, 2026-11-07). Эндпоинтов пока нет. Источник правды после Phase 1 — генерируемая схема OpenAPI (`/api/schema/`).

## Соглашения
- Префикс `/api/v1/`, JSON, `snake_case`.
- Аутентификация — сессия (cookie) + CSRF для браузера.
- Ошибки: `{ "error": { "code": "...", "message": "...", "details": {...}, "request_id": "..." } }`.
- Пагинация — курсорная для лент (чат, события), постраничная для каталога.
- Идемпотентность для мутаций с деньгами: заголовок `Idempotency-Key`.
- Деньги: `{ "amount_minor": 150000, "currency": "RUB" }`.

## Планируемые группы (по фазам)
| Группа | Фаза |
|---|---|
| `health/` | 1 |
| `auth/`, `me/` | 2 |
| `social-accounts/`, `social-accounts/{id}/refresh/`, `social-accounts/{id}/statistics/` | 3–4 |
| `offers/`, `networks/` | 4 |
| `catalog/` | 5 |
| `orders/`, `orders/{id}/items/{item}/proof/`, `.../confirm/`, `.../check-publication/` | 6 |
| `payments/`, `payments/webhooks/{provider}/` | 7 |
| `chats/`, `notifications/` | 8 |
| `disputes/`, `support/tickets/` | 9 |
| `staff/...` | 9–10 |
| `reviews/` | 11 |

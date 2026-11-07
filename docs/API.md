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

## Реализовано (Phase 1–2)

| Метод | Путь | Доступ | Назначение |
|---|---|---|---|
| GET | `/health/live`, `/health/ready` | все | Проверка работоспособности |
| GET | `/auth/csrf`, `/auth/session` | все | CSRF-cookie; текущий пользователь или `null` |
| POST | `/auth/register` | все | Регистрация (`email, password, display_name, as_seller, accept_terms`) |
| POST | `/auth/login`, `/auth/logout` | все | Вход / выход |
| POST | `/auth/verify-email`, `/auth/resend-verification` | все / вошедший | Подтверждение email |
| POST | `/auth/password-reset`, `/auth/password-reset/confirm` | все | Сброс пароля |
| POST | `/auth/password-change` | вошедший | Смена пароля |
| GET/PATCH | `/me` | вошедший | Профиль, роли, разрешения |
| POST | `/me/become-seller` | вошедший | Добавить роль продавца |
| GET | `/me/{purchases,sales,accounts,networks,reviews,tickets,notifications,activity}` | вошедший | Кабинет (только свои данные) |
| POST | `/me/notifications/{id}/read` | вошедший | Прочитать уведомление |
| PUT | `/staff/users/{id}/roles` | `user.manage_roles` | Назначить роли (с комментарием, в журнал) |

Ограничение частоты запросов: область `auth` (`THROTTLE_AUTH`, по умолчанию 10/мин).

## Реализовано (Phase 3–5)

| Метод | Путь | Доступ |
|---|---|---|
| POST | `/social-accounts` | продавец |
| GET | `/social-accounts/{id}`, `/social-accounts/{id}/statistics` | владелец |
| POST | `/social-accounts/{id}/refresh`, `/social-accounts/{id}/manual-statistics` | владелец |
| GET/POST | `/social-accounts/oauth/tiktok/start`, `/social-accounts/oauth/tiktok/callback` | продавец |
| PATCH/DELETE | `/social-accounts/{id}/manage` | владелец |
| POST | `/social-accounts/{id}/listing` `{listed}` | владелец |
| GET/POST | `/social-accounts/{id}/offers`; PATCH `/offers/{id}` | владелец |
| GET | `/social-accounts/{id}/orders` | владелец |
| GET/POST | `/networks`; GET/PATCH `/networks/{id}`; POST `/networks/{id}/items`; DELETE `/networks/{id}/items/{item}` | владелец |
| GET | `/ad-formats` | все |
| GET | `/catalog/home`, `/catalog/accounts`, `/catalog/accounts/{id}`, `/catalog/networks`, `/catalog/networks/{id}`, `/sellers/{id}` | все |

Фильтры `/catalog/accounts`: `q, platform, followers_min/max, avg_min/max, price_min/max (копейки), category, language, geo, ad_format, verified=1, rating_min, sort=new|popular|price_asc|price_desc|followers|views`.

## Реализовано (Phase 6–13), кратко

Заказы: `POST /orders`, `GET /orders/{id}`, `…/events`, `…/terms`, `…/terms/propose`, `…/terms/{p}/decide`, `…/cancel`, `…/materials-delivered`, `…/items/{i}/{accept|decline|ready|proof|confirm|rework|cancel|check-publication|review|report}`.
Платежи: `POST /orders/{id}/pay`, `POST /payments/webhooks/{provider}`, `GET /me/payouts`, `POST /me/payouts/{id}/{withdraw|retry}`.
Чат и файлы: `GET/POST /orders/{id}/chat`, `PATCH/DELETE /orders/{id}/chat/{m}`, `POST /files`, `GET /files/{id}`.
Споры: `GET /dispute-reasons`, `POST /orders/{id}/disputes/open`, `GET /orders/{id}/disputes`, `GET /disputes/{id}`, `POST /disputes/{id}/{reply|appeal}`; поддержка `POST /support/tickets`.
Сотрудники: `/staff/disputes[/{id}[/{action}]]`, `/staff/tickets`, `/staff/dashboard`, `/staff/users`, `/staff/accounts`, `/staff/orders`, `/staff/audit[/verify]`, `/staff/reviews`, `/staff/fraud-signals`.
Отзывы: `POST /reviews/{id}/{reply|complain}`. Phase 13: `/me/{favorites|viewed|recommendations|analytics|referrals}`, `GET /catalog/compare?ids=`.
Полная схема — `/api/schema/` (OpenAPI).

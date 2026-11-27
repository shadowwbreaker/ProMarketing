# API

Актуальные маршруты и форматы описывает генерируемая схема OpenAPI (`/api/schema/`). Ниже приведены правила интеграции и сводка маршрутов.

## Соглашения
- Префикс `/api/v1/`, JSON, `snake_case`.
- Аутентификация — сессия (cookie) + CSRF. Перед `POST /auth/login`, `/auth/register` и отправкой токенов восстановления или подтверждения получите cookie через `GET /auth/csrf`. Передавайте её значение в `X-CSRFToken`. Запросы с постороннего Origin или без CSRF получают 403.
- Ошибки: `{ "error": { "code": "...", "message": "...", "details": {...}, "request_id": "..." } }`.
- Пагинация — курсорная для лент (чат, события), постраничная для каталога.
- Для `POST /orders` передайте уникальный `Idempotency-Key` (1–128 видимых ASCII-символов). Повтор того же заказа с тем же ключом возвращает 201 и ID исходного заказа. Если содержимое запроса изменилось, вернётся 409 `idempotency_conflict`. Ключ действует для одного покупателя. Старые клиенты могут отправлять запрос без ключа, на них защита от повтора не действует.
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

- `GET /messages/conversations` возвращает по одной строке на собеседника. `GET /messages/conversations/{user}` объединяет личную переписку и сообщения оплаченных заказов этой пары, сохраняя ссылки на заказы. `before` загружает предыдущую страницу, `version` позволяет проверить наличие изменений, а `read=1` отмечает ленту собеседника прочитанной при её открытии.
- `GET /messages/status` возвращает признак непрочитанного, признак полученных заказов и время последнего входящего сообщения и заказа для звуковых уведомлений.
- `GET /orders/{id}/chat?read=1` отмечает уведомления об оплате и сообщениях только для текущего участника и заказа. У новых оплаченных заказов исходное ТЗ доступно в сообщении `order_brief`. Оно ссылается на первую версию условий.
- `GET /orders/received` возвращает оплаченные заказы продавца и статистику по выбранным фильтрам `number`, `buyer`, `status`, `platform`. `format_csv=1` выгружает отфильтрованный список.
Споры: `GET /dispute-reasons`, `POST /orders/{id}/disputes/open`, `GET /orders/{id}/disputes`, `GET /disputes/{id}`, `POST /disputes/{id}/{reply|appeal}`; поддержка `POST /support/tickets`.
Сотрудники: `/staff/disputes[/{id}[/{action}]]`, `/staff/tickets`, `/staff/dashboard`, `/staff/users`, `/staff/accounts`, `/staff/orders`, `/staff/audit[/verify]`, `/staff/reviews`, `/staff/fraud-signals`.
Отзывы: `POST /reviews/{id}/{reply|complain}`. Phase 13: `/me/{favorites|viewed|recommendations|analytics|referrals}`, `GET /catalog/compare?ids=`.
Полная схема — `/api/schema/` (OpenAPI).

## Актуализация · 18 ноября 2026

Phase 13 выше — исторический перечень: /catalog/compare, /me/viewed, /me/recommendations удалены D-022. Актуальные маршруты поддержки — таблица API [TECH_SUPPORT_LOCAL](TECH_SUPPORT_LOCAL.md). GET/PUT /staff/users/{id}/roles управляет ролями выбранного подтверждённого пользователя с комментарием. Старый disputes/open не обходит referral/assignee/arbitration.work. Апелляция неверного типа:400, конфликт интересов:403, лимит:429, отказ лимитера:503. [Подробности](RELEASE_2026-11-18.md).

## TOTP QR · 22 ноября 2026

Контракты /me/2fa, /me/2fa/setup, /me/2fa/confirm и /me/2fa/disable сохранены. setup возвращает прежние secret и otpauth_url только текущему авторизованному пользователю; QR не передаётся по сети как картинка, а строится клиентом из otpauth_url. Для всех ответов этой view добавлен запрет кэширования (private, no-store, no-cache и Expires). Новых маршрутов и миграций нет. Подтверждение шестизначного кода остаётся серверным условием включения.

## Уточнения по аудиту беты · 27 ноября 2026

- `GET /api/v1/health/live` проверяет HTTP-процесс без обращений к зависимостям. `GET /api/v1/health/ready` возвращает активные проверки PostgreSQL и Redis с локальным кэшем до 5 секунд на процесс. Ответы сохранены: 200 для `ok`, 503 для `degraded`.
- Для 2FA в JSON передавайте шестизначный код строкой, например `"012345"`. Некорректный тип или формат отклоняется как ошибка клиента. При входе без кода для аккаунта с 2FA сохраняется ответ `401 otp_required`.

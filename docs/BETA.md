# Бета-версия (ветка `beta`, D-025)

Бета предназначена для некоммерческого тестирования. Оплата имитируется: после покупки пользователь видит экран «Оплата подтверждена», а в чате появляются «Заказ создан» и «Оплата получена». Об имитации сообщается при оформлении и подтверждении.

## Чем бета отличается от основной ветки

Только конфигурацией, код тот же:

| Переменная | Бета | Боевая версия |
|---|---|---|
| `BETA_MODE` | `true` | `false` |
| `PAYMENT_PROVIDER` | `mock` (обязательно при `BETA_MODE`) | адаптер провайдера (ЮKassa / Т-Бизнес) |
| `DEV_AUTO_VERIFY_EMAIL` | можно `true`, если нет SMTP | запрещено |

**Переход на рабочую версию:** подключить адаптер провайдера (Q-03), поставить `BETA_MODE=false`, `PAYMENT_PROVIDER=<провайдер>`, настроить SMTP — и перезапустить. Приложение само откажется стартовать, если что-то осталось в бета-режиме. Тестовые заказы беты стоит удалить или перенести в отдельную БД до запуска.

## Запуск на сервере

1. VPS в РФ (2 vCPU, 4 ГБ RAM достаточно), Docker и Docker Compose, домен с двумя A-записями: `beta.<домен>` и `api.beta.<домен>` → IP сервера.
2. `git clone -b beta https://github.com/shadowwbreaker/ProMarketing.git && cd ProMarketing`
3. `cp .env.beta.example .env.prod` и заполнить пустые значения (ключи, домены, пароль БД, S3, SMTP).
4. `docker compose -f infra/docker-compose.prod.yml --env-file .env.prod up -d --build` — Caddy сам получит HTTPS-сертификаты.
5. `docker compose -f infra/docker-compose.prod.yml --env-file .env.prod exec backend python manage.py createsuperuser` — администратор.
6. Проверка: `https://api.beta.<домен>/api/v1/meta` → `{"beta": true, ...}`, откройте сайт, добавьте свой канал.

**TikTok:** в приложении TikTok Developers укажите Redirect URI `https://beta.<домен>/account/accounts/oauth/tiktok`; пока приложение на проверке — включите Sandbox и добавьте тестовые аккаунты в Target users.

Для публичной беты используйте `python manage.py seed_beta_catalog` с `BETA_MODE=true` и `PAYMENT_PROVIDER=mock`. Команда добавляет пять явно помеченных каналов и две сетки. Публичные ссылки ведут на примеры, цены и цифры условные, владельцы каналов не участвуют в сделках. Демо-продавец без возможности входа. Локальный `seed_demo` остаётся для разработки.

## Проверка

`node frontend/e2e/beta.cjs` (backend запущен с `BETA_MODE=true`): вход → «Купить» → «Оплата подтверждена» → в чате «Оплата получена».

# TESTING

Статус: Phase 14 (2026-11-07). Статус `[v] VERIFIED` в roadmap ставится только при прошедшем тесте.

## Итог

| Набор | Количество | Результат |
|---|---|---|
| Backend pytest (unit, integration, API, БД, гонки) | 144 | все проходят, покрытие 91% (порог CI — 85%) |
| Frontend Vitest | 9 | проходят |
| Типы / линтер / сборка | `tsc`, `eslint`, `ruff`, `next build` | без ошибок |
| E2E Playwright | 9 наборов | проходят (`npm run e2e`) |

## Запуск

```bash
# backend (нужен PostgreSQL, DATABASE_URL)
cd backend && pytest --cov

# frontend
cd frontend && npm test && npm run typecheck && npm run lint && npm run build

# e2e: backend + celery worker + seed + frontend
cd backend
python manage.py seed_demo
THROTTLE_AUTH=300/min THROTTLE_ANON=100000/min python manage.py runserver   # e2e логинится и ходит по страницам чаще, чем разрешает защита
celery -A config worker -l warning                     # в другом терминале
cd ../frontend && npm run build && npm start           # в третьем
npm i -D playwright && npx playwright install chromium # один раз
npm run e2e
```

CI: `.github/workflows/ci.yml` — ruff, проверка миграций, pytest с покрытием, eslint, tsc, vitest, сборка.

## Сценарии roadmap 14.3

| Сценарий | E2E | Backend |
|---|---|---|
| A — продавец: регистрация → аккаунт → статистика → предложение → сетка → заказ → публикация → завершение | `auth.cjs`, `accounts.cjs`, `order.cjs` | `test_phase3_*`, `test_phase4_*`, `test_full_lifecycle_and_payout_hold` |
| B — покупатель: регистрация → каталог → фильтры → заказ → оплата → подтверждение → отзыв | `auth.cjs`, `catalog.cjs`, `order.cjs` | `test_phase5_*`, `test_phase6_*`, `test_phase11_*` |
| C — арбитраж: оплата → невыполнение → жалоба → уведомление → решение → операция провайдера → история | `dispute.cjs` | `test_phase9_disputes.py` (15 сценариев) |

## Дополнительные тесты roadmap 14.4

| Пункт | Тест |
|---|---|
| Покупка всей сетки | `test_network_order_whole_and_partial` |
| Покупка одного аккаунта из сетки | `test_network_order_whole_and_partial` |
| Частичное выполнение сетки | `test_partial_network_fulfilment_refunds_only_failed_item`, `test_s05_partial_network_dispute` |
| Частичный возврат | `test_no_double_refund_and_partial_refunds`, `test_s03_brief_mismatch_partial_refund_seller_keeps_rest` |
| Продавец не отвечает | `test_s01_seller_not_responding` |
| Покупатель не подтверждает | `test_confirmation_window_auto_confirm_or_ticket`, `test_s06_buyer_not_confirming_seller_wins` |
| Видео удалено раньше срока | `test_s04_removed_early_during_hold`, `test_s04_after_payout_is_documented_limitation` |
| Ошибка парсера | `test_error_does_not_destroy_previous_statistics` |
| Обновление при предыдущей успешной статистике | `test_refresh_interval_enforced_and_shown`, `test_error_does_not_destroy_previous_statistics` |
| Повторный webhook | `test_payment_only_via_verified_webhook`, `test_parallel_duplicate_webhooks_processed_once` |
| Повторный запрос возврата | `test_no_double_refund_and_partial_refunds`, `test_parallel_full_refunds_execute_once` |
| Несанкционированный доступ к чужому заказу | `test_cross_user_access_is_denied`, `test_anonymous_cannot_reach_private_endpoints` |
| Одновременное открытие нескольких споров | `test_simultaneous_disputes_on_different_items`, `test_parallel_disputes_on_same_item_single_active` |

## Frontend 14.2

| Проверка | Где |
|---|---|
| Страницы, формы, фильтры, пользовательские сценарии | e2e-наборы выше |
| Адаптивность | `responsive.cjs`: 23 страницы × 375 и 1280 px — без горизонтальной прокрутки и ошибок выполнения |
| Загрузка и ошибки | Vitest (`StatusPanel`, `LoginPage`), e2e проверяет отсутствие `pageerror` |

## Найдено и исправлено в Phase 14

- Шапка сотрудника не помещалась на ширине 375 px (+83 px) — исправлено.
- Необработанные ошибки загрузки на страницах сеток, антифрода, дашборда, сравнения и в панелях кабинета — теперь показывается сообщение об ошибке.
- Нестабильный e2e избранного (зависел от предыдущего запуска) — сделан идемпотентным.

## Не проверено

- Живые API TikTok и YouTube и реальный платёжный провайдер — нужны ключи и договор (EXT-1, Q-03).
- `docker compose up` на Windows — нужен запуск у пользователя.
- Нагрузочное тестирование — не проводилось.


## Регрессии после аудита беты 15 ноября

- `backend/tests/test_beta_security_regressions.py` проверяет анонимный CSRF, сессии TOTP, параллельные повторы заказа, карантин, ответы ClamAV, подтверждение email и перенос статусов.
- `frontend/e2e/security.cjs` отправляет формы с отключённым JavaScript и проверяет, что пароль не попадает в URL. Для общего набора E2E используйте отдельную базу с демо-данными и `DEV_AUTO_VERIFY_EMAIL=false`.
- [Отчёт о выпуске](TEST_REPORT_2026-11-15.md) содержит результаты повторной проверки, процедуры для Vercel и ограничения проверки.

## Актуализация · 18 ноября 2026

Обычный Docker без seed. E2E: отдельный проект/том, освободить 3000/8000 остановкой обычного проекта без удаления томов, затем docker compose -p promarketing-release-test -f infra/docker-compose.yml -f infra/docker-compose.test.yml up -d --build. Никогда не подключать override к реальной БД/Neon. После проверки остановить тестовый проект и запустить обычный без override. Проверки: pytest, ruff, makemigrations --check, lint, typecheck, npm test (Vitest + Node glob), build, node e2e/run-all.cjs с Playwright/Chromium. [Результаты](RELEASE_2026-11-18.md).
Тестовый override задаёт THROTTLE_AUTH=120/min для серии входов E2E; реальный предел анонимного каталога остаётся 300/min и проверяется отдельно. Для специального e2e/beta.cjs выставьте E2E_BETA_MODE=true перед пересозданием backend тестового проекта; для остальных сценариев оставьте false. Браузер можно выбрать E2E_BROWSER_CHANNEL=msedge, если Playwright Chromium не установлен. Значения NODE_PATH/путь Playwright зависят от вашего окружения.

## QR-подключение 2FA · 22 ноября 2026

Проверки формы — frontend/tests/twofactor.test.tsx (реальный SVG, ручной fallback, ошибка/успех подтверждения, повторное нажатие, уже включённый фактор). Серверные регрессии — tests/test_phase15_2fa.py и tests/test_beta_security_regressions.py. Для локального сквозного теста: frontend/e2e/twofactor.cjs, Playwright с Chromium либо E2E_BROWSER_CHANNEL=msedge. jsqr используется только тестом; растеризация SVG выполняется sharp из зависимостей Next.js. QR декодируется независимым алгоритмом, затем проверяются неверный/правильный код и обязательный TOTP при следующем входе.

E2E_BASE_URL и E2E_API_URL должны указывать на изолированный локальный сервис: скрипт запрещает публичные хосты. Он создаёт одноразового тестового пользователя, поэтому не запускайте его против пользовательской БД. Секрет/URI не выводятся, изображение обрабатывается в памяти. При E2E_BACKEND_CONTAINER проверяется также отсутствие этих значений в логах указанного локального контейнера. Тест не включён в общий runner, чтобы не создавать учётки в обычном локальном сервисе.

Результат 22 ноября: 18/18 серверных тестов выбранного набора, 13/13 Vitest и 2/2 Node glob, ESLint/TypeScript/production build успешны. Сквозной сценарий проверен на production-сборке локального сайта: QR независимо декодируется в исходный URI; ручной ключ совпадает; неверный код отклоняется, правильный включает 2FA; следующий вход без TOTP отклоняется и с правильным TOTP проходит. Проверены ширины 320/375/1280, отсутствие секрета в URL запросов и логах API. Телефон с установленным Google Authenticator в автоматической проверке не использовался; проверена стандартная совместимость формата.

## Проверки исправлений аудита · 27 ноября 2026

- Серверные регрессии проверяют числовые и нетекстовые значения 2FA на подтверждении, входе и отключении. Добавлена проверка кэша readiness, повторного использования degraded и восстановления после обновления кэша.
- Production на Vercel проверяется отдельно от Docker. Для настроек Vercel штатное значение `THROTTLE_ANON` составляет 3000/min, для локальной конфигурации — 300/min. Пограничные WAF-правила имеют свои пороги. Проверяйте активную конфигурацию обоих проектов в Vercel и штатные ответы без нагрузки на публичные URL.
- После смены домена проверяйте CSRF на основном адресе, CORS прямого API, переход с домена без `www`, ссылки подтверждения email и TikTok OAuth, соглашение, политику и файлы проверки префиксов. Полная матрица адресов в [BETA_VERCEL](BETA_VERCEL.md).


Локальный прогон исправлений: 208 серверных тестов на PostgreSQL 16, Ruff и `makemigrations --check --dry-run` прошли. На исходной бете отдельно прошли 14 штатных браузерных сценариев, QR-настройка 2FA и бета-покупка с объединённым диалогом.

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
THROTTLE_AUTH=300/min python manage.py runserver      # e2e логинится чаще, чем разрешает защита (10/мин)
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

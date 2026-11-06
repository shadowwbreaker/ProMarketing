# DATABASE

Статус: проект схемы (Phase 0, 2026-11-07). Базы данных и миграций пока нет. PostgreSQL 16 (DECISIONS D-001).

Общие правила:
- PK — `UUID` (не раскрывает объёмы и порядок).
- `created_at`, `updated_at` (`timestamptz`) во всех таблицах.
- Деньги — `BIGINT` в минимальных единицах + `currency CHAR(3)`; `CHECK (amount_minor >= 0)`.
- Статусы — `TEXT` + `CHECK` по списку (или PostgreSQL enum), переходы проверяет сервисный слой.
- Мягкое удаление (`deleted_at`) там, где есть история; append-only таблицы не удаляются и не изменяются.

## 1. Пользователи и права

| Таблица | Ключевые поля | Ограничения/индексы |
|---|---|---|
| `users` | email, password_hash, is_email_verified, status (active/limited/blocked), last_seen_at | `UNIQUE lower(email)` |
| `user_profiles` | user_id, display_name, bio, avatar, country, language | `UNIQUE user_id` |
| `roles`, `permissions`, `role_permissions`, `user_roles` | buyer, seller, support_agent, moderator, admin, super_admin | `UNIQUE (user_id, role_id)` |
| `user_sanctions` | user_id, type (warning/limit/block), reason, starts_at, ends_at, created_by, dispute_id? | индекс (user_id, ends_at) |

## 2. Социальные аккаунты и статистика

| Таблица | Ключевые поля | Ограничения/индексы |
|---|---|---|
| `social_accounts` | owner_id, platform (tiktok/instagram/youtube), external_id, handle, profile_url, title, category, language, geo, description, status, is_listed | `UNIQUE (platform, external_id)` — один аккаунт не выставить дважды |
| `social_account_connections` | social_account_id, oauth_scopes, access_token_enc, refresh_token_enc, expires_at, revoked_at | токены зашифрованы |
| `stats_refresh_jobs` | social_account_id, requested_by, status (queued/running/succeeded/failed), error_code, error_message, started_at, finished_at | частичный `UNIQUE (social_account_id) WHERE status IN ('queued','running')` |
| `social_account_statistics` | social_account_id, job_id, followers, avg_views, videos_in_sample, source (api/manual/vendor), trust_status (VERIFIED/MANUAL/STALE/UNAVAILABLE/SUSPICIOUS/ERROR), fetched_at, expires_at | индекс (social_account_id, fetched_at DESC); только добавление |
| `social_videos` | statistics_id, external_video_id, url, published_at, views, likes, comments, duration_s, is_short_heuristic | `UNIQUE (statistics_id, external_video_id)` |

`social_accounts.current_statistics_id` — ссылка на последнюю успешную запись (для каталога), обновляется только при успехе.

## 3. Предложения и сетки

| Таблица | Ключевые поля | Ограничения |
|---|---|---|
| `advertising_offers` | social_account_id, ad_format, price_minor, currency, conditions, placement_days, is_active | `CHECK price_minor > 0` |
| `account_networks` | owner_id, title, description, total_price_minor?, conditions, allow_partial_purchase, is_active | |
| `network_items` | network_id, social_account_id, offer_id, price_minor | `UNIQUE (network_id, social_account_id)`; аккаунт принадлежит владельцу сетки (проверка в сервисе + триггер) |

## 4. Заказы

| Таблица | Ключевые поля | Ограничения |
|---|---|---|
| `orders` | buyer_id, seller_id, network_id?, status (агрегированный), total_minor, currency, current_terms_version_id | индекс (buyer_id), (seller_id), (status) |
| `order_terms_versions` | order_id, version, brand, site_url, brief, ad_text, cta, links, publish_deadline, placement_days, materials, platform_removal_policy, agreed_by_buyer_at, agreed_by_seller_at, hash | `UNIQUE (order_id, version)`; только добавление |
| `order_items` | order_id, social_account_id, offer_id, price_minor, status (DRAFT…EXPIRED из roadmap 6.2), publish_deadline, placement_until, accepted_at | `CHECK price_minor > 0`; `SUM(order_items.price_minor) = orders.total_minor` — проверка в сервисе |
| `publication_proofs` | order_item_id, video_url, profile_url, screenshot_file_id, published_at, submitted_by | |
| `publication_checks` | order_item_id, trigger (proof/buyer/admin/window_end/placement_end), result (found/not_found/unavailable/error), checked_at | лимит ручных проверок — в сервисе |
| `order_events` | order_id, order_item_id?, actor_id, type, from_status, to_status, payload, prev_hash, hash | append-only |

## 5. Платежи

| Таблица | Ключевые поля | Ограничения |
|---|---|---|
| `payments` | order_id, provider, provider_payment_id, amount_minor, status, idempotency_key | `UNIQUE (provider, provider_payment_id)`, `UNIQUE idempotency_key` |
| `payment_allocations` | payment_id, order_item_id, amount_minor | сумма = платёж |
| `refund_requests` | order_item_id, dispute_decision_id?, amount_minor, status, provider_refund_id, idempotency_key | `UNIQUE idempotency_key`; сумма возвратов по позиции ≤ оплачено |
| `payouts` | order_item_id, seller_id, amount_minor, kind (main/holdback), status, provider_payout_id, idempotency_key | `UNIQUE idempotency_key`; `UNIQUE (order_item_id, kind)` |
| `payment_webhook_events` | provider, provider_event_id, type, raw_body, signature_valid, processed_at | `UNIQUE (provider, provider_event_id)` |
| `financial_ledger_entries` | order_item_id, kind, amount_minor, provider_ref, created_at | append-only; отражает операции провайдера |

## 6. Чаты и уведомления

| Таблица | Ключевые поля |
|---|---|
| `chats` | order_id (`UNIQUE`), locked_at (при споре) |
| `chat_messages` | chat_id, author_id, kind (user/system), body, revision, deleted_at |
| `chat_message_revisions` | message_id, body, created_at (история правок) |
| `attachments` | owner_id, storage_key, mime, size, sha256, scan_status |
| `notifications` | user_id, type, payload, read_at |

## 7. Поддержка и споры

| Таблица | Ключевые поля |
|---|---|
| `support_tickets` | author_id, order_id?, category, status, priority, assignee_id |
| `dispute_reasons` | code, title, allowed_for (buyer/seller), required_fields |
| `disputes` | order_id, opened_by, reason_id, status (OPEN…APPEALED), priority, assignee_id, response_due_at, appeal_of_id? |
| `dispute_items` | dispute_id, order_item_id — `UNIQUE (order_item_id) WHERE dispute активен` |
| `dispute_messages` | dispute_id, author_id, visibility (all/staff), body |
| `dispute_evidence` | dispute_id, submitted_by, attachment_id?, url?, description, sha256 |
| `dispute_decisions` | dispute_id, order_item_id, decision_type, refund_amount_minor?, comment (NOT NULL), decided_by |
| `dispute_actions` | decision_id, action_type, status, refund_request_id?, payout_id? |
| `admin_notes` | subject_type, subject_id, author_id, body (видны только сотрудникам) |

## 8. Отзывы и аудит

| Таблица | Ключевые поля | Ограничения |
|---|---|---|
| `reviews` | order_item_id, author_id, target_user_id, rating 1–5, text, seller_reply, moderation_status | `UNIQUE (order_item_id, author_id)` |
| `review_complaints` | review_id, author_id, reason, status | |
| `audit_logs` | actor_id, action, subject_type, subject_id, before, after, reason, comment, ip, prev_hash, hash | append-only; роль приложения без UPDATE/DELETE |
| `admin_actions` | представление/подмножество `audit_logs` для действий сотрудников | |

## 9. Дополнения к списку roadmap (Phase 1)

Roadmap перечисляет 23 модели. Для выполнения требований других фаз дополнительно нужны: `social_account_connections`, `stats_refresh_jobs`, `order_terms_versions`, `publication_proofs`, `publication_checks`, `order_events`, `payment_allocations`, `payment_webhook_events`, `financial_ledger_entries`, `attachments`, `chat_message_revisions`, `dispute_reasons`, `dispute_items`, `dispute_messages`, `dispute_decisions`, `dispute_actions`, `admin_notes`, роли/разрешения, `review_complaints`.

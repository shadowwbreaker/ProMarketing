# SOCIAL DATA — получение статистики социальных аккаунтов

Статус документа: исследование Phase 0; реализация Phase 3 — 2026-11-07 (см. §8).

## 1. Принципы (из roadmap, обязательны)

- Сбор только по действию пользователя: добавление аккаунта или кнопка «Обновить статистику». Никакого расписания и мониторинга.
- Только разрешённые способы: официальные API, лицензированные поставщики, ручной ввод с маркировкой.
- Запрещено: обход CAPTCHA и антибот-защиты, чужие cookies/сессии/аккаунты, скрейпинг страниц вопреки условиям платформы.
- Неподтверждённые данные не получают статус `VERIFIED`.

## 2. Результаты исследования по платформам

### 2.1. TikTok

| Вопрос | Ответ |
|---|---|
| Официальный API | **Display API** + Login Kit (OAuth владельца) |
| Подписчики | `follower_count` в `/v2/user/info/`, scope `user.info.stats` |
| Последние видео | `POST /v2/video/list/`, scope `video.list`, сортировка по дате создания (новые первыми), постраничная выдача (`cursor`, `has_more`; в примере `max_count: 20`) |
| Просмотры видео | `view_count` (int64) в объекте видео; также `create_time`, `duration`, `share_url` |
| Без авторизации владельца | **Нет** для коммерческого продукта. Research API предназначен для некоммерческих исследований и не подходит |
| Требования | Регистрация приложения в TikTok for Developers, одобрение Login Kit и Display API, проверка приложения |
| Отличие Reels/Shorts-аналога | Все видео TikTok короткие; отдельного фильтра не нужно |

**Вывод:** TikTok реализуем через OAuth владельца. Статус платформы: `[ ] NOT STARTED`, внешняя зависимость — одобрение приложения TikTok.

### 2.2. Instagram (Reels)

| Вопрос | Ответ |
|---|---|
| Официальный API | Instagram Platform (Graph API). Basic Display API закрыт |
| С авторизацией владельца | Instagram API with Instagram Login: собственные медиа и insights профессионального аккаунта |
| Без авторизации владельца | **Business Discovery**: `followers_count`, `media_count`, по медиа — `like_count`, `comments_count`, `view_count` для других профессиональных аккаунтов. Требует собственного профессионального аккаунта приложения и прохождения App Review |
| Ограничения | Только Business/Creator аккаунты; age-gated аккаунты не возвращаются; `view_count` включает платные и органические просмотры; ID медиа из Business Discovery нельзя запросить напрямую |
| Выделение Reels | По типу медиа (`media_product_type`) — проверить в реализации |

**Вывод:** технически реализуем; основной путь — OAuth владельца (подтверждает и владение). Business Discovery — только как вспомогательный способ проверки при споре.

**Блокер юрисдикции:** в РФ с 2025-09-01 запрещено размещать рекламу на информационных ресурсах организаций, признанных экстремистскими (Meta, т. е. Instagram и Facebook). Запрет касается рекламодателей, блогеров и посредников. Если целевой рынок — РФ, направление Instagram `[!] BLOCKED` до юридического решения (DECISIONS Q-01, D-007).

### 2.3. YouTube Shorts

| Вопрос | Ответ |
|---|---|
| Официальный API | YouTube Data API v3 |
| Подписчики | `channels.list` → `statistics.subscriberCount` (публичные данные, без OAuth владельца, по API-ключу; может быть скрыт владельцем) |
| Последние видео | Плейлист загрузок канала → `videos.list` (`statistics.viewCount`, `contentDetails.duration`) |
| Без авторизации владельца | Да, для публичных данных |
| Отличие Shorts | **Официального поля «это Shorts» нет.** Признак — длительность (Shorts до 3 минут) и вертикальный формат; эвристика может ошибаться. Помечать выборку как «определено по длительности» |
| Ключевое ограничение | Политики YouTube API: запрещены независимо рассчитанные (derived) метрики и агрегирование данных для показа третьим лицам без одобрения. Среднее просмотров последних 15 видео, показанное рекламодателям, — именно такая метрика |
| Одобрение | С 2026-06-01 — через форму расширения квоты (Section 5, use case «Analytics & Reporting»). При одобрении статистику можно хранить до 36 месяцев |
| Хранение без одобрения | Ограничено 30 днями (данные нужно обновить или удалить) |
| Запрещено также | Рейтинги/«битвы» каналов, оценки рекламных CPM и платных просмотров, выдача своих чисел за данные YouTube |

**Вывод:** API доступен, но коммерческий показ среднего требует одобрения YouTube. До одобрения — `[!] BLOCKED` для production; разработка и тесты допускаются. Решение — DECISIONS D-006, Q-05.

Подтверждение владения каналом: Google OAuth (`youtube.readonly`) → `channels.list?mine=true`.

## 3. Альтернативы, если официального способа нет или он не одобрен

1. **Лицензированный поставщик данных** (агрегаторы с договором с платформами). Перед подключением: проверить, как поставщик получает данные; при скрейпинге без согласия платформы — не использовать.
2. **Ручной ввод владельцем** → `MANUAL`, отдельная маркировка в каталоге, фильтр «только подтверждённая статистика» их исключает.
3. **Скриншоты аналитики от владельца** + проверка модератором → всё равно `MANUAL` (не `VERIFIED`).

## 4. Архитектура модуля `social_data`

```
backend/social_data/
  core/
    provider.py        # абстрактный SocialDataProvider
    types.py           # нормализованные DTO: AccountSnapshot, VideoSnapshot
    errors.py          # ProviderUnavailable, RateLimited, AuthExpired, NotProfessionalAccount ...
    registry.py        # платформа -> провайдер
  providers/
    tiktok/  instagram/  youtube/  manual/
  services/
    refresh_service.py # лимиты, блокировки, запуск одного цикла, сохранение
    averages.py        # расчёт среднего (чистая функция)
    url_parser.py      # распознавание платформы по ссылке
  models.py
  tests/
```

Интерфейс провайдера (из roadmap 3.6): `validate_profile_url()`, `resolve_account()`, `get_account_statistics()`, `get_recent_videos(limit=15)`, `get_video_statistics()`, `normalize_response()`, `check_data_availability()`.

Провайдеры не знают друг о друге; общая логика (лимиты, сохранение, расчёт) — только в `services/`.

## 5. Алгоритм обновления (один цикл)

1. Пользователь нажимает «Обновить» → API проверяет право на аккаунт.
2. В транзакции: `SELECT … FOR UPDATE` строки аккаунта; проверка, что нет активной задачи и что прошёл интервал (`STATS_REFRESH_INTERVAL`, по умолчанию 24 ч). Иначе — отказ с причиной и временем следующей попытки.
3. Создаётся `StatsRefreshJob(status=QUEUED)`; уникальный частичный индекс «одна активная задача на аккаунт» исключает гонки.
4. Воркер выполняет один цикл: подписчики → последние 15 подходящих видео → просмотры.
5. Среднее = сумма просмотров / число полученных видео (целочисленно, с округлением вниз, хранится и число видео).
6. Успех → новая запись `SocialAccountStatistics` + 15 `SocialVideoSnapshot`. Ошибка → запись в `StatsRefreshJob.error`, предыдущая успешная статистика не трогается.
7. Задача завершается; повторов по расписанию нет. Повтор при сетевой ошибке — не более N раз в рамках этого же цикла.

## 6. Статусы статистики

`VERIFIED` (официальный API + OAuth владельца), `MANUAL`, `STALE` (старше настраиваемого порога; для YouTube без одобрения — 30 дней), `UNAVAILABLE`, `SUSPICIOUS` (сигнал антифрода — резкий рост, расхождение с ручными данными), `ERROR` (последняя попытка неуспешна; показывается вместе с последней успешной).

## 7. Хранение токенов

OAuth-токены шифруются на уровне приложения (ключ из секретов окружения), доступ — только сервису `social_data`. Отключение аккаунта → отзыв токена у платформы и удаление.

## 8. Реализация (Phase 3)

| Компонент | Файл | Статус |
|---|---|---|
| Интерфейс провайдера | `backend/social_data/core/provider.py` | реализован, тесты |
| Парсер ссылок | `core/url_parser.py` | реализован, тесты |
| TikTok (Display API, Login Kit) | `providers/tiktok/provider.py` | реализован, контрактные тесты; живой API не проверен (нет ключей) |
| YouTube (Data API v3) | `providers/youtube/provider.py` | реализован, контрактные тесты; живой API не проверен (нет ключа) |
| Instagram | `providers/instagram/provider.py` | `[!] BLOCKED` (D-013) |
| Fake (dev/test) | `providers/fake/provider.py` | запрещён в production |
| Ручной ввод | `providers/manual/provider.py` | статус MANUAL |
| Сервис обновления | `services/refresh_service.py` | лимиты, история, SUSPICIOUS |
| Задачи | `tasks.py` | `run_refresh_job` (разовая), `purge_expired_youtube_data` (только удаление) |

Порог SUSPICIOUS: рост подписчиков ×3 или средних просмотров ×5 между обновлениями. Аккаунт уходит на проверку модератору (`under_review`) — это сигнал, а не обвинение.

API: `POST /social-accounts`, `GET /social-accounts/{id}`, `POST /social-accounts/{id}/refresh`, `GET /social-accounts/{id}/statistics`, `POST /social-accounts/{id}/manual-statistics`, `GET /social-accounts/oauth/tiktok/start`, `POST /social-accounts/oauth/tiktok/callback`.

## Источники

- TikTok Display API: https://developers.tiktok.com/doc/display-api-get-started/
- TikTok, перенос полей в `user.info.stats`: https://developers.tiktok.com/bulletin/user-info-scope-migration
- TikTok Video Object: https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object
- Instagram Business Discovery: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery
- YouTube Developer Policies Guide: https://developers.google.cn/youtube/terms/developer-policies-guide?hl=en
- YouTube Derived Metrics Policy: https://developers.google.cn/youtube/terms/derived-metrics-policy
- YouTube Terms revision history: https://developers.google.com/youtube/terms/revision-history
- Запрет рекламы в Instagram (РБК): https://rbc.ru/society/07/04/2025/67f3c1569a79478b85f9f1ec

## Согласие владельца (D-024, 2026-11-09)

Перед каждым запросом к API платформы (добавление канала, «Обновить статистику», вход через TikTok) владелец ставит галочку согласия; сервер без `consent: true` запрос не выполняет и сохраняет запись `StatsConsent`. Покупатели видят сырые просмотры последних 15 видео; среднее по YouTube — после одобрения сценария Analytics & Reporting (D-016).

## Подключение настоящих API (2026-11-09)

`SOCIAL_PROVIDER_MODE=auto` (по умолчанию в dev): платформа работает через настоящий API, как только заданы её ключи; иначе — демо-цифры с явной пометкой «Демо-режим» в интерфейсе. Production принимает только `official`.

**YouTube** — нужен **API-ключ** (не OAuth-клиент): Google Cloud Console → APIs & Services → Library → включить «YouTube Data API v3» → Credentials → Create credentials → **API key** → ограничить ключ API «YouTube Data API v3». В `.env`: `YOUTUBE_API_KEY=...`. Один пересчёт = 3 единицы квоты (из 10 000 в сутки): channels.list → playlistItems.list (50 последних загрузок) → videos.list; Shorts определяются по длительности ≤ 180 с, берутся 15 последних.

**TikTok** — приложение на developers.tiktok.com: продукты Login Kit + Display API, scopes `user.info.basic`, `user.info.stats`, `video.list`; Redirect URI = `{FRONTEND_URL}/account/accounts/oauth/tiktok` (TikTok принимает только HTTPS-адреса, поэтому нужен домен или HTTPS-туннель, `localhost` не подойдёт); приложение проходит проверку TikTok. В `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`. После этого мастер после галочки согласия сразу ведёт на вход через TikTok.

# ProMarketing

Маркетплейс рекламы у авторов TikTok и YouTube Shorts (Instagram Reels отключён для рынка РФ — см. `docs/DECISIONS.md` D-013).

Главный документ — [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md). Решения — [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Запуск в Docker (Windows: Docker Desktop + WSL2)

```bash
cp .env.example .env        # заполните FIELD_ENCRYPTION_KEY
docker compose -f infra/docker-compose.yml up --build
docker compose -f infra/docker-compose.yml exec backend python manage.py seed_demo   # демо-данные
```
Сервисы: db, redis, backend, worker (фоновые задачи), beat (таймеры заказов и выплат), frontend.
Демо-входы: `demo-buyer@example.com`, `demo-seller1@example.com`, `demo-admin@example.com`, `demo-support@example.com`, пароль `Demo-password-1`.
Backend: http://localhost:8000/api/v1/health/ready · Frontend: http://localhost:3000 · Статус: http://localhost:3000/status

## Запуск без Docker

Нужны PostgreSQL 16 и Redis 7.

```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
pytest

cd ../frontend
npm ci
npm run dev        # npm test · npm run typecheck · npm run lint · npm run build
```

В режиме разработки используются тестовые провайдеры: `SOCIAL_PROVIDER_MODE=fake` и `PAYMENT_PROVIDER=mock`. В production они запрещены — приложение не стартует.

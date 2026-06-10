# Cool Finances — Telegram-бот для личных финансов

v1.5: учёт трат, кредиты, проценты, what-if симуляции, прогнозы, напоминания, OCR чеков, мультивалютные переводы.

## Возможности

- Текстовый ввод трат и доходов (`кофе 200 динар`, `зарплата 180000`)
- Фото чеков (OpenAI Vision)
- Счета: дебет, кредитка, наличные, долг
- Кредитные условия и `/interest` — сколько теряешь на процентах
- What-if: «что будет, если 50к на кредитку?»
- Прогнозы: `/forecast`, «могу ли iPhone в следующем месяце?»
- Напоминания: аренда, налоги, кредиты
- Переводы между счетами (в т.ч. кросс-валютные через `/set_rate`)
- Подушка безопасности

## Локальный запуск

```bash
cp .env.example .env
# BOT_TOKEN=... (от @BotFather)
# OPENAI_API_KEY=... (опционально, для OCR и умного парсинга)

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

docker compose up -d
python -m src.main poll          # разработка
# или
python -m src.main               # API + webhook
python -m src.main worker        # напоминания
```

## Деплой на Railway

### 1. Создай проект

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Добавь плагины: **PostgreSQL**, **Redis**

### 2. Сервис `web` (бот)

Переменные окружения:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | токен от @BotFather |
| `WEBHOOK_URL` | `https://<your-app>.up.railway.app` |
| `WEBHOOK_SECRET` | случайная строка |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` → замени `postgresql://` на `postgresql+asyncpg://` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `OPENAI_API_KEY` | опционально |

**Обязательно:** `REDIS_URL` должен ссылаться на Redis-плагин, не оставляй дефолт `localhost:6379`.
В Railway → сервис → Variables → `REDIS_URL` = `${{Redis.REDIS_URL}}` (имя сервиса Redis может отличаться — смотри в Reference).

**Важно:** Railway выдаёт `DATABASE_URL` как `postgresql://...` — в Variables замени на:
```
postgresql+asyncpg://user:pass@host:port/db
```

Start command (из `railway.toml`):
```
uvicorn src.api.app:app --host 0.0.0.0 --port $PORT
```

### 3. Сервис `worker` (напоминания)

- Duplicate service или New Service из того же репо
- Те же env vars, **включая `REDIS_URL=${{Redis.REDIS_URL}}`**
- Start command: `python -m src.main worker`
- Или используй `railway.worker.toml`

### 4. Проверка

```bash
curl https://<your-app>.up.railway.app/health
# {"status":"ok","version":"1.5.0"}
```

Открой бота в Telegram → `/start`

### 5. Локальная отладка webhook

```bash
ngrok http 8000
# WEBHOOK_URL=https://xxxx.ngrok.io
uvicorn src.api.app:app --reload
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/add_account` | Добавить счёт |
| `/balance` | Балансы |
| `/transfer` | Перевод |
| `/set_rate RSD EUR 117.5` | Курс валют |
| `/debts` | Долги |
| `/interest` | Потери на процентах |
| `/credit_terms` | Условия кредита |
| `/forecast` | Прогноз на месяц |
| `/remind` | Создать напоминание |
| `/reminders` | Список напоминаний |
| `/goals` | Цели / подушка |
| `/report` | Расходы |
| `/history` | История операций и редактирование |

## Структура

```
src/
  advisor/     # проценты, what-if, прогнозы
  bot/         # Telegram handlers
  workers/     # ARQ напоминания
  parsers/     # intent, текст, напоминания
  services/    # бизнес-логика
```

## Стек

Python 3.9+, aiogram 3, FastAPI, PostgreSQL, Redis, ARQ, OpenAI (опционально)

# Async Health Checker

Асинхронный агрегатор статусов: REST API принимает список URL, кладёт задачу в очередь
Redis Streams, фоновый воркер конкурентно проверяет доступность адресов через httpx
и складывает результаты в PostgreSQL.

## Архитектура

```
клиент ──POST /api/v1/task──> FastAPI ──XADD──> Redis Stream ──XREADGROUP──> worker
                                 │                                             │
                                 │                                        httpx-проверки
                                 ▼                                             ▼
клиент ──GET /api/v1/task/{id}── PostgreSQL <──── tasks / check_results ───────┘
```

* **API** (`main.py`) — приём задач и выдача результатов, ничего не проверяет сам.
* **Worker** (`python -m worker`) — отдельный процесс, потребитель consumer group.
  Масштабируется горизонтально: каждое сообщение достаётся ровно одному воркеру.
* **tasks** — состояние задачи (`queued` → `processing` → `completed` / `failed`).
* **check_results** — результат проверки каждого URL.

## Быстрый старт

```bash
docker compose up -d --build
```

Поднимутся шесть сервисов: `postgres`, `redis`, одноразовый `migrate` (накатывает миграции
Alembic), `app`, `worker` и `prometheus`. Приложение доступно на `http://localhost:8000`,
Swagger — на `http://localhost:8000/docs`, Prometheus — на `http://localhost:9090`.

Несколько воркеров:

```bash
docker compose up -d --scale worker=3
```

Остановка (данные сохраняются в томах):

```bash
docker compose down
```

## Примеры запросов

Создание задачи:

```bash
curl -X POST http://localhost:8000/api/v1/task -H "Content-Type: application/json" -d "{\"urls\": [\"https://ya.ru\", \"https://google.com\", \"https://github.com\"]}"
```

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "urls_count": 3,
  "created_at": "2026-08-20T10:30:00Z"
}
```

Получение результатов:

```bash
curl http://localhost:8000/api/v1/task/550e8400-e29b-41d4-a716-446655440000
```

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_urls": 3,
  "processed_urls": 3,
  "results": [
    {
      "url": "https://ya.ru/",
      "status_code": 200,
      "response_time": 145.3,
      "is_available": true,
      "error_message": null,
      "checked_at": "2026-08-20T10:30:05Z"
    },
    {
      "url": "https://github.com/",
      "status_code": null,
      "response_time": null,
      "is_available": false,
      "error_message": "Connection timeout",
      "checked_at": "2026-08-20T10:30:12Z"
    }
  ]
}
```

Коды ответов: `201` — задача создана, `200` — статус получен, `404` — задачи нет,
`422` — невалидный список URL, `503` — очередь недоступна.

## Метрики

```bash
curl http://localhost:8000/metrics
```

| Метрика | Тип | Источник |
|---|---|---|
| `http_requests_total` | counter | prometheus-fastapi-instrumentator |
| `http_request_duration_seconds` | histogram | prometheus-fastapi-instrumentator |
| `tasks_processed_total` | gauge | счётчик в Redis, инкрементирует воркер |
| `tasks_failed_total` | gauge | счётчик в Redis |
| `urls_checked_total{status}` | gauge | счётчик в Redis, метки `available` / `unavailable` |
| `active_workers` | gauge | heartbeat-ключи воркеров с TTL |
| `queue_size` | gauge | `XLEN` стрима задач |

Счётчики воркеров живут в Redis, поэтому один эндпоинт отдаёт корректные суммарные
значения при любом числе воркеров и переживает их перезапуск.

### Prometheus

Сервер разворачивается вместе со стеком, конфигурация — [prometheus.yml](prometheus.yml),
интервал сбора 15 секунд, срок хранения 15 дней. Состояние сбора:
`http://localhost:9090/targets`, консоль запросов — `http://localhost:9090/graph`.

Примеры запросов:

```promql
tasks_processed_total
queue_size
urls_checked_total{status="unavailable"}
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## Локальная разработка

Нужны запущенные PostgreSQL и Redis. Настройки берутся из `src/.env`:

```bash
copy src\.env.example src\.env
```

В шаблоне только две обязательные переменные, значения — плейсхолдеры.
Для локальной разработки заполняются так:

```
APP_CONFIG__DB__URL=postgresql+asyncpg://postgres:admin@localhost:5432/async_health_checker
APP_CONFIG__REDIS__URL=redis://localhost:6379/0
```

Остальные параметры имеют значения по умолчанию и описаны в разделе
[Конфигурация](#конфигурация) — добавляйте в `.env` только те, что нужно изменить.

Для `docker compose` отдельный шаблон в корне — [.env.example](.env.example): пароль
PostgreSQL и публикуемые порты. Он необязателен, у всех значений есть дефолты.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd src
..\.venv\Scripts\alembic upgrade head
```

Два процесса, оба запускаются из каталога `src`:

```bash
..\.venv\Scripts\python -m uvicorn main:app --reload
```

```bash
..\.venv\Scripts\python -m worker
```

## Конфигурация

Все переменные имеют префикс `APP_CONFIG__`, вложенность задаётся `__`.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_CONFIG__DB__URL` | — | DSN PostgreSQL (обязательна) |
| `APP_CONFIG__REDIS__URL` | — | DSN Redis (обязательна) |

## Тесты

Нужен запущенный PostgreSQL: тесты создают и удаляют базу `async_health_checker_test`.

```bash
cd src
..\.venv\Scripts\python -m pytest
```

С покрытием:

```bash
..\.venv\Scripts\python -m pytest --cov --cov-report=term
```

## Надёжность

* **Доставка ровно одному воркеру** — consumer group Redis Streams.
* **Восстановление после падения** — неподтверждённые сообщения подбирает `XAUTOCLAIM`.
* **Битые сообщения** не роняют воркер: уходят в `health_checker:tasks:dlq`.
* **Ретраи** — до `MAX_ATTEMPTS` попыток, затем задача помечается `failed`.
* **Graceful shutdown** — по SIGTERM воркер дорабатывает текущий батч и закрывает соединения.
* **Логи** — JSON, в каждой записи задачи присутствует `task_id`.

## Структура проекта

```
src/
├── api/v1/            эндпоинты (по файлу на endpoint)
├── broker/            клиент Redis и продюсер
├── database/          движок, модели SQLAlchemy
├── logging_setup/     конфигурация structlog
├── migration/         Alembic
├── monitoring/        метрики Prometheus и счётчики
├── repositories/      доступ к данным
├── schemas/           Pydantic-схемы (по файлу на схему)
├── services/          бизнес-логика
├── tests/             pytest
└── worker/            консьюмер и цикл обработки
```

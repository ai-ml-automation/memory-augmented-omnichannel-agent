# 🛠️ DEVELOPMENT_GUIDE.md

## 1. Введение

### 1.1. Обзор проекта

«Омниканальный агент с долговременной памятью» — это система, объединяющая текстовые и голосовые каналы (MAX, Telegram, VK, телефония) с единым AI‑агентов, который запоминает факты о клиентах и использует их для персонализированных ответов. Проект построен на Python (FastAPI) и React (TypeScript), использует PostgreSQL, Redis, Qdrant, Neo4j и MinIO.

Данное руководство описывает настройку окружения для разработки, запуск сервисов, работу с миграциями, тестирование, линтинг и отладку.

### 1.2. Требования к системе

Перед началом убедитесь, что установлены следующие компоненты:

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| **Python** | 3.12+ | Рекомендуется 3.12.4 |
| **Node.js** | 20 LTS | Для фронтенда |
| **Docker** | 24+ | Для контейнеризации сервисов |
| **Docker Compose** | 2.20+ | Для оркестрации локальной инфраструктуры |
| **Git** | 2.40+ | Для управления репозиторием |
| **Make** (опционально) | — | Для упрощения команд |

### 1.3. Структура репозитория

Основные директории:

```
project-root/
├── backend/                # Бэкенд (FastAPI)
│   ├── src/                # Исходный код
│   │   ├── api/            # Роутеры
│   │   ├── services/       # Бизнес-логика
│   │   ├── agents/         # LangGraph агенты
│   │   ├── integrations/   # Внешние интеграции
│   │   ├── tasks/          # Celery задачи
│   │   └── utils/          # Утилиты (крипто, Presidio)
│   ├── tests/              # Тесты (unit, integration, e2e, load)
│   ├── alembic/            # Миграции БД
│   └── requirements.txt    # Зависимости Python
├── frontend/               # Фронтенд (React)
│   ├── src/
│   │   ├── app/            # Точка входа, роутинг
│   │   ├── pages/          # Страницы
│   │   ├── components/     # UI-компоненты
│   │   ├── store/          # Zustand стейт
│   │   └── api/            # Axios клиент
│   └── package.json        # Зависимости фронтенда
├── docker-compose.yml      # Все сервисы для локальной разработки
├── .env.example            # Шаблон переменных окружения
└── k8s/                    # Манифесты для Kubernetes (production)
```

Подробное описание всех файлов см. в [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

---

## 2. Настройка локального окружения

### 2.1. Клонирование репозитория

```bash
git clone <repository-url>
cd memory-augmented-omnichannel-agent-local
```

### 2.2. Настройка переменных окружения

Скопируйте шаблон и заполните необходимые параметры (для разработки можно оставить значения по умолчанию):

```bash
cp .env.example .env
```

Ключевые переменные (все подробно описаны в [.env.example](../.env.example)):

| Переменная | Назначение | Значение по умолчанию |
|------------|------------|------------------------|
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `postgres` |
| `REDIS_HOST` | Хост Redis | `localhost` |
| `QDRANT_URL` | URL Qdrant | `http://localhost:6333` |
| `NEO4J_URI` | URI Neo4j | `bolt://localhost:7687` |
| `ENABLE_LLM` | Включить LLM | `false` (для быстрого старта) |
| `ENABLE_VOICE` | Включить голос | `false` |
| `ENABLE_MEMORY` | Включить память | `false` |

Для разработки рекомендуется оставить все `ENABLE_*` в `false`, чтобы не загружать тяжёлые модели и не тратить ресурсы. При необходимости их можно включить позже.

### 2.3. Установка зависимостей

#### Бэкенд

Рекомендуется использовать виртуальное окружение:

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# или venv\Scripts\activate     # Windows

pip install --upgrade pip
pip install -r requirements.txt
```

#### Фронтенд

```bash
cd frontend
npm ci                           # чистая установка из package-lock.json
# или npm install, если lock-файла нет
```

---

## 3. Запуск с Docker Compose

### 3.1. Запуск всех сервисов (рекомендуемый способ)

Поднимает все необходимые базы данных (PostgreSQL, Redis, Qdrant, Neo4j, MinIO) и сам бэкенд с фронтендом:

```bash
docker compose up -d
```

После запуска проверьте доступность:

- Бэкенд: [http://localhost:8000/health](http://localhost:8000/health) — должен вернуть `{"status":"healthy"}`
- Фронтенд: [http://localhost:3000](http://localhost:3000)
- Swagger (документация API): [http://localhost:8000/docs](http://localhost:8000/docs)
- Qdrant: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- Neo4j Browser: [http://localhost:7474](http://localhost:7474) (логин: `neo4j`, пароль: `password`)

### 3.2. Запуск с профилем мониторинга

Для разработки и отладки может потребоваться стек мониторинга (Prometheus, Grafana, Loki, Jaeger):

```bash
docker compose --profile monitoring up -d
```

После запуска:

- Grafana: [http://localhost:3001](http://localhost:3001) (логин: `admin`, пароль: `admin`)
- Prometheus: [http://localhost:9090](http://localhost:9090)
- Jaeger: [http://localhost:16686](http://localhost:16686)

### 3.3. Запуск только инфраструктуры (без бэкенда)

Если вы хотите запускать бэкенд локально (вне Docker), а базы данных оставить в контейнерах:

```bash
docker compose up -d postgres redis qdrant neo4j minio
```

Затем запустите бэкенд локально (см. раздел 4).

### 3.4. Остановка сервисов

```bash
docker compose down
# или с очисткой томов (удаление данных БД):
docker compose down -v
```

---

## 4. Локальный запуск без Docker

### 4.1. Базы данных

Если вы не хотите использовать Docker для инфраструктуры, можно установить PostgreSQL, Redis, Qdrant, Neo4j и MinIO локально. Однако Docker Compose — рекомендуемый способ для единообразия.

### 4.2. Запуск бэкенда

Убедитесь, что виртуальное окружение активировано и переменные окружения загружены (можно использовать `source .env` или экспортировать вручную).

```bash
cd backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload` — автоматическая перезагрузка при изменении кода.
- Сервер будет доступен на `http://localhost:8000`.

### 4.3. Запуск Celery воркеров и Beat (для асинхронных задач)

В отдельном терминале:

```bash
cd backend
celery -A src.celery_app worker --loglevel=info --concurrency=4
```

В ещё одном терминале (для планировщика):

```bash
celery -A src.celery_app beat --loglevel=info
```

### 4.4. Запуск фронтенда

```bash
cd frontend
npm run dev
```

Сервер будет доступен на `http://localhost:3000`.

---

## 5. Миграции БД (Alembic)

Все изменения схемы БД управляются через Alembic. Таблицы **не** создаются автоматически при старте приложения.

### 5.1. Применение всех миграций (создание таблиц)

```bash
cd backend
alembic upgrade head
```

### 5.2. Создание новой миграции после изменения моделей

Если вы изменили модели в [backend/src/models.py](../backend/src/models.py), сгенерируйте новую миграцию:

```bash
alembic revision --autogenerate -m "краткое описание изменений"
```

Проверьте сгенерированный файл в `alembic/versions/` и при необходимости отредактируйте его вручную.

### 5.3. Откат миграции

```bash
alembic downgrade -1
```

### 5.4. Просмотр истории миграций

```bash
alembic history
```

### 5.5. Важные замечания

- Все миграции должны быть проверены на тестовой БД перед применением на production.
- Для разработки можно использовать SQLite (изменяется `DATABASE_URL` в `.env`), но для точного соответствия production рекомендуется использовать PostgreSQL.
- Текущие миграции находятся в `backend/alembic/versions/`:
  - `001_initial_schema.py` — начальная схема (все таблицы).
  - `002_remove_encrypted_data.py` — удаление поля `encrypted_data` из Fact.

---

## 6. Тестирование

### 6.1. Модульные тесты (Unit)

Запуск всех модульных тестов:

```bash
cd backend
pytest tests/unit/ -v
```

Запуск конкретного теста:

```bash
pytest tests/unit/test_auth_service.py -v
```

Модульные тесты используют SQLite in‑memory и не требуют работающих сервисов.

### 6.2. E2E-тесты

E2E-тесты проверяют полные сценарии через API. Для их запуска необходима работающая инфраструктура (можно использовать Docker Compose).

```bash
pytest tests/e2e/ -v
```

По умолчанию E2E-тесты используют SQLite in‑memory (быстро, но не полностью отражает поведение PostgreSQL). Для запуска на реальной PostgreSQL установите переменную окружения:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/omnichannel_test \
  pytest tests/e2e/ -v
```

### 6.3. Интеграционные тесты

Проверяют взаимодействие с внешними сервисами (БД, Qdrant, Neo4j, Celery). Требуют запущенных зависимостей.

```bash
pytest tests/integration/ -v
```

Некоторые интеграционные тесты помечены `@pytest.mark.skipif`, если соответствующие флаги отключены (например, `ENABLE_VOICE=false`).

### 6.4. Контрактные тесты

Проверяют структуру payload'ов вебхуков и ответов LLM:

```bash
pytest tests/integration/test_contract_webhooks.py -v
pytest tests/unit/test_llm_parsing.py -v
```

### 6.5. Нагрузочное тестирование (Locust)

Для проверки производительности используется Locust:

```bash
cd backend
locust -f tests/load/locustfile.py --host http://localhost:8000
```

Откройте `http://localhost:8089`, укажите количество пользователей и скорость запуска.

### 6.6. Запуск всех тестов

```bash
cd backend
pytest tests/ -v
```

---

## 7. Линтинг и форматирование

### 7.1. Python (Ruff)

Проверка кода:

```bash
cd backend
ruff check src/ --select E,F,I
ruff format --check src/
```

Автоисправление:

```bash
ruff check src/ --fix
ruff format src/
```

Настройки линтера: `pyproject.toml` (или `ruff.toml`). Используются только правила E (ошибки PEP8), F (Pyflakes), I (сортировка импортов). Максимальная длина строки — 100 символов.

### 7.2. TypeScript / React (ESLint + Prettier)

```bash
cd frontend
npm run lint        # проверка
npm run lint:fix    # автоисправление
```

### 7.3. Проверка типов (TypeScript)

```bash
cd frontend
npx tsc --noEmit
```

---

## 8. Отладка

### 8.1. VS Code

Создайте `.vscode/launch.json` для отладки бэкенда:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": ["src.main:app", "--reload"],
            "cwd": "${workspaceFolder}/backend",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        },
        {
            "name": "Python: Celery Worker",
            "type": "python",
            "request": "launch",
            "module": "celery",
            "args": ["-A", "src.celery_app", "worker", "--loglevel=info"],
            "cwd": "${workspaceFolder}/backend"
        }
    ]
}
```

### 8.2. Логи

- **Backend логи**: `docker compose logs -f backend` или локально — вывод в терминал.
- **Celery логи**: `docker compose logs -f celery-worker` или отдельный терминал.
- **Логи БД**: `docker compose logs -f postgres`.

Логи структурированы в JSON в production-режиме, но в разработке выводятся в читаемом текстовом формате.

### 8.3. Swagger (OpenAPI)

После запуска бэкенда откройте `http://localhost:8000/docs`. Интерактивная документация позволяет тестировать API прямо из браузера.

### 8.4. Доступ к базам данных

- **PostgreSQL**: `docker compose exec postgres psql -U postgres -d omnichannel`
- **Redis**: `docker compose exec redis redis-cli`
- **Qdrant**: REST API `http://localhost:6333` или веб-интерфейс `/dashboard`
- **Neo4j**: `http://localhost:7474` (логин: `neo4j`, пароль: `password`)

---

## 9. Часто задаваемые вопросы

### Q: Почему я получаю `ModuleNotFoundError` при запуске тестов?

Убедитесь, что PYTHONPATH настроен:

```bash
export PYTHONPATH="<корень_проекта>"
```

Или используйте `python -m pytest tests/` вместо просто `pytest`.

### Q: Как сбросить базу данных до чистого состояния?

```bash
docker compose down -v   # удаляет тома с данными
docker compose up -d postgres
alembic upgrade head
```

### Q: Почему `/health` показывает `degraded`?

Проверьте, что все сервисы (postgres, redis, qdrant, neo4j) работают:

```bash
docker compose ps
```

Если какой-то сервис не запущен, запустите его отдельно:

```bash
docker compose up -d qdrant
```

### Q: Как включить LLM для локального тестирования?

В `.env` установите `ENABLE_LLM=true` и укажите API-ключи (например, для YandexGPT). Затем перезапустите бэкенд.

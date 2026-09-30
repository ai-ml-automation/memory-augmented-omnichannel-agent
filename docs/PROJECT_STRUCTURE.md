# 🌳 PROJECT_STRUCTURE.md

## 1. Введение

Данный документ содержит полное дерево директорий и файлов проекта «Омниканальный агент с долговременной памятью» с кратким описанием назначения каждого файла. Он предназначен для быстрого ориентирования в структуре репозитория, поиска нужных модулей и понимания организации кода.

---

## 2. Дерево проекта

```
memory-augmented-omnichannel-agent-local/
├── .github/                                    # GitHub конфигурация
│   └── workflows/                              # CI/CD пайплайны
│       └── ci.yml                              # GitHub Actions: линтеры, тесты, сборка образов
├── backend/                                    # Бэкенд (Python / FastAPI)
│   ├── alembic/                                # Миграции БД (Alembic)
│   │   ├── versions/                           # Файлы миграций
│   │   │   ├── 001_initial_schema.py           # Начальная схема (6 таблиц)
│   │   │   └── 002_remove_encrypted_data.py    # Удаление поля encrypted_data из Fact
│   │   ├── env.py                              # Асинхронное окружение Alembic
│   │   └── script.py.mako                      # Шаблон для создания миграций
│   ├── src/                                    # Исходный код
│   │   ├── agents/                             # LangGraph-агенты
│   │   │   ├── __init__.py
│   │   │   ├── conflict_resolver.py            # Разрешение конфликтов (HITL)
│   │   │   ├── fact_extractor.py               # Извлечение фактов (LLM + Presidio)
│   │   │   ├── memory_manager.py               # Управление памятью (DI через MemoryService)
│   │   │   └── response_generator.py           # Генерация ответов (LLM + fallback)
│   │   ├── api/                                # FastAPI роутеры
│   │   │   ├── __init__.py
│   │   │   ├── admin_channels.py               # Управление каналами (admin)
│   │   │   ├── admin_users.py                  # Управление пользователями (admin)
│   │   │   ├── analytics.py                    # Аналитика и дашборды
│   │   │   ├── auth.py                         # Аутентификация (JWT, CSRF)
│   │   │   ├── chat.py                         # Чат (ChatService)
│   │   │   ├── consents.py                     # Согласие (152-ФЗ) + RTBF
│   │   │   ├── health.py                       # Health-проверки
│   │   │   ├── memory.py                       # Операции с памятью
│   │   │   ├── voice.py                        # Голосовой пайплайн + WebSocket
│   │   │   └── webhooks.py                     # Вебхуки (MAX, Telegram, VK)
│   │   ├── integrations/                       # Внешние интеграции
│   │   │   ├── __init__.py
│   │   │   ├── max_gateway.py                  # MAX (aiomax)
│   │   │   ├── telegram_gateway.py             # Telegram (aiogram)
│   │   │   ├── vk_gateway.py                   # VK (vk_api)
│   │   │   └── voice_gateway.py                # Голос / CTI
│   │   ├── services/                           # Бизнес-логика
│   │   │   ├── __init__.py
│   │   │   ├── analytics_service.py            # Аналитические запросы
│   │   │   ├── audit_service.py                # Аудит (152-ФЗ)
│   │   │   ├── auth_service.py                 # Аутентификация (bcrypt, JWT, версионирование)
│   │   │   ├── channel_binding_service.py      # Привязка каналов
│   │   │   ├── chat_service.py                 # Логика чата
│   │   │   ├── consent_service.py              # Согласие (152-ФЗ)
│   │   │   ├── fact_service.py                 # CRUD фактов + шифрование + аудит
│   │   │   ├── graph_relationships.py          # Enum типов отношений (Cypher injection fix)
│   │   │   ├── graph_service.py                # Neo4j (асинхронный драйвер)
│   │   │   ├── llm_service.py                  # LLM (YandexGPT, vLLM, GigaChat)
│   │   │   ├── mem0_memory_service.py          # Реализация MemoryService
│   │   │   ├── memory_search_service.py        # Гибридный поиск + реранкинг
│   │   │   ├── memory_service.py               # Абстрактный MemoryService
│   │   │   ├── message_handler.py              # Обработка сообщений
│   │   │   ├── message_router.py               # Маршрутизация по каналам
│   │   │   ├── prompt_builder.py               # Построение промптов
│   │   │   ├── response_evaluator.py           # Оценка качества ответов
│   │   │   ├── right_to_be_forgotten_service.py # RTBF (каскадное удаление)
│   │   │   ├── session_service.py              # Управление сессиями
│   │   │   ├── silero_tts.py                   # TTS (Silero, ленивая загрузка)
│   │   │   ├── speech_service.py               # ASR/TTS (Yandex SpeechKit)
│   │   │   ├── vector_store_service.py         # Qdrant (эмбеддинги, пул потоков)
│   │   │   ├── voice_service.py                # Голосовой пайплайн
│   │   │   └── whisper_asr.py                  # ASR (Whisper, ленивая загрузка)
│   │   ├── tasks/                              # Celery задачи
│   │   │   ├── __init__.py
│   │   │   ├── decay_tasks.py                  # DecayAgent (плавное устаревание)
│   │   │   ├── fact_tasks.py                   # Извлечение фактов
│   │   │   └── message_tasks.py                # Обработка сообщений
│   │   ├── utils/                              # Утилиты
│   │   │   ├── __init__.py
│   │   │   ├── crypto.py                       # AES-256-GCM шифрование
│   │   │   ├── presidio_anonymizer.py          # Анонимизация PII (Presidio)
│   │   │   └── presidio_russian.py             # Русские recognizers (паспорт, СНИЛС, ИНН)
│   │   ├── __init__.py
│   │   ├── celery_app.py                       # Celery приложение + Beat
│   │   ├── config.py                           # Pydantic Settings + Feature Flags + Vault
│   │   ├── database.py                         # SQLAlchemy engine + async session
│   │   ├── dependencies.py                     # FastAPI зависимости (get_current_admin)
│   │   ├── logging_config.py                   # JSON-логи + PII-редикция
│   │   ├── main.py                             # Точка входа FastAPI (lifespan)
│   │   ├── metrics.py                          # Prometheus метрики
│   │   ├── middleware.py                       # JWT middleware
│   │   ├── models.py                           # Все SQLAlchemy модели
│   │   ├── schemas.py                          # Pydantic схемы (граница API)
│   │   ├── tracing.py                          # OpenTelemetry + Jaeger
│   │   └── vault_client.py                     # HashiCorp Vault клиент
│   ├── tests/                                  # Тесты
│   │   ├── e2e/                                # E2E-тесты
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py                     # Фикстуры (PostgreSQL / SQLite)
│   │   │   ├── test_auth_e2e.py                # Аутентификация (7 тестов)
│   │   │   ├── test_chat_e2e.py                # Чат (4 теста)
│   │   │   ├── test_consents_e2e.py            # Согласие (3 теста)
│   │   │   ├── test_health_e2e.py              # Health (1 тест)
│   │   │   └── test_webhooks_e2e.py            # Вебхуки (секреты)
│   │   ├── fixtures/                           # Тестовые данные
│   │   │   └── audio/
│   │   │       ├── generate_audio.py           # Генерация test.wav (440Hz)
│   │   │       └── test.wav                    # Аудио-фикстура для голосовых тестов
│   │   ├── integration/                        # Интеграционные тесты
│   │   │   ├── __init__.py
│   │   │   ├── test_celery_integration.py      # Celery (4 теста)
│   │   │   ├── test_contract_webhooks.py       # Контракты вебхуков (4 теста)
│   │   │   ├── test_encryption_integration.py  # Шифрование (3 теста)
│   │   │   ├── test_vector_store_integration.py # Vector Store (sys.modules моки)
│   │   │   └── test_voice_integration.py       # Голосовой пайплайн
│   │   ├── load/                               # Нагрузочное тестирование (Locust)
│   │   │   ├── __init__.py
│   │   │   ├── locustfile.py                   # Сценарии (Health, Auth, Chat)
│   │   │   └── README.md                       # Инструкция по запуску
│   │   ├── unit/                               # Модульные тесты
│   │   │   ├── __init__.py
│   │   │   ├── test_agents.py                  # LangGraph-агенты (DI)
│   │   │   ├── test_auth_cookie_security.py    # Cookie + CSRF
│   │   │   ├── test_auth_service.py            # AuthService
│   │   │   ├── test_celery_tasks.py            # Celery задачи
│   │   │   ├── test_chat_service.py            # ChatService
│   │   │   ├── test_cors_config.py             # CORS
│   │   │   ├── test_crypto.py                  # Шифрование
│   │   │   ├── test_fact_service.py            # FactService
│   │   │   ├── test_llm_parsing.py             # LLM JSON парсинг
│   │   │   ├── test_memory_service.py          # MemoryService
│   │   │   ├── test_presidio_anonymizer.py     # Presidio
│   │   │   ├── test_right_to_be_forgotten.py   # RTBF
│   │   │   ├── test_silero_tts.py              # Silero TTS
│   │   │   ├── test_voice_service.py           # VoiceService
│   │   │   ├── test_webhook_security.py        # Безопасность вебхуков
│   │   │   └── test_whisper_asr.py             # Whisper ASR
│   │   ├── __init__.py
│   │   └── conftest.py                         # Глобальные фикстуры (SQLite)
│   ├── alembic.ini                             # Конфигурация Alembic
│   └── requirements.txt                        # Зависимости Python
├── config/                                     # Конфигурации сервисов
│   ├── grafana/                                # Grafana provisioning
│   │   └── provisioning/
│   │       ├── dashboards/
│   │       │   ├── json/
│   │       │   │   ├── business.json           # Бизнес-дашборд (память, NPS, AHT)
│   │       │   │   └── omnichannel-backend.json # Технический дашборд (задержки, ошибки)
│   │       │   └── dashboards.yml
│   │       └── datasources.yml                 # Datasources: Prometheus, Loki
│   ├── loki.yml                                # Loki конфигурация
│   ├── prometheus-rules.json                   # Правила алертов (6 алертов)
│   ├── prometheus.yml                          # Prometheus scrape config
│   └── promtail.yml                            # Promtail (сбор логов Docker)
├── docs/                                       # Документация
├── frontend/                                   # Фронтенд (React / TypeScript)
│   ├── src/
│   │   ├── api/
│   │   │   └── axios.ts                        # Axios клиент + интерсепторы + AbortController
│   │   ├── app/
│   │   │   └── App.tsx                         # React Router + AnimatePresence
│   │   ├── components/
│   │   │   ├── ui/                             # shadcn/ui компоненты
│   │   │   │   ├── alert.tsx                   # Alert (с вариантами)
│   │   │   │   ├── badge.tsx                   # Badge (default, secondary, destructive, outline)
│   │   │   │   ├── button.tsx                  # Button (CVA variants)
│   │   │   │   ├── card.tsx                    # Card (Header, Title, Content, Footer)
│   │   │   │   ├── input.tsx                   # Input
│   │   │   │   ├── skeleton.tsx                # Skeleton (загрузка)
│   │   │   │   ├── switch.tsx                  # Switch (toggle)
│   │   │   │   └── table.tsx                   # Table (Header, Body, Row, Cell)
│   │   │   ├── Layout.test.tsx                 # Юнит-тесты Layout (6 тестов)
│   │   │   ├── Layout.tsx                      # Responsive Layout + sidebar + ThemeToggle
│   │   │   ├── ThemeToggle.tsx                 # Переключение тёмной/светлой темы
│   │   │   └── VoiceInput.tsx                  # Запись аудио (MediaRecorder API)
│   │   ├── features/                           # FSD фичи (заглушки)
│   │   │   ├── auth/
│   │   │   ├── consent/
│   │   │   └── memory/
│   │   ├── lib/
│   │   │   ├── utils.ts                        # cn() — clsx + tailwind-merge
│   │   │   ├── validations.test.ts             # Тесты Zod схем (9 тестов)
│   │   │   └── validations.ts                  # Zod схемы (login, register, consent)
│   │   ├── pages/                              # Страницы
│   │   │   ├── admin/
│   │   │   │   └── settings.tsx                # Административные настройки
│   │   │   ├── audit/
│   │   │   │   └── index.tsx                   # Аудит-лог (фильтры, пагинация)
│   │   │   ├── dashboard/
│   │   │   │   └── index.tsx                   # Дашборд (согласие, статистика)
│   │   │   ├── forget/
│   │   │   │   └── index.tsx                   # Право на забвение (RTBF)
│   │   │   ├── login/
│   │   │   │   └── index.tsx                   # Вход (react-hook-form + zod)
│   │   │   ├── memory/
│   │   │   │   └── index.tsx                   # Просмотр памяти (таблица + граф)
│   │   │   ├── operator/                       # Операторский дашборд
│   │   │   │   ├── sessions/
│   │   │   │   │   └── SessionDetail.tsx       # Детали сессии (сообщения, факты)
│   │   │   │   ├── analytics.tsx               # Аналитика (Recharts)
│   │   │   │   ├── channels.tsx                # Управление каналами
│   │   │   │   ├── index.tsx                   # Панель оператора
│   │   │   │   └── users.tsx                   # Управление пользователями
│   │   │   ├── profile/
│   │   │   │   └── index.tsx                   # Профиль пользователя (согласие, пароль)
│   │   │   ├── register/
│   │   │   │   └── index.tsx                   # Регистрация (react-hook-form + zod)
│   │   │   ├── sessions/
│   │   │   │   └── index.tsx                   # Список сессий (фильтры, пагинация)
│   │   │   └── voice-test/
│   │   │       └── index.tsx                   # Тест голосового пайплайна (ASR → LLM → TTS)
│   │   ├── shared/                             # Общие компоненты и типы
│   │   │   ├── lib/
│   │   │   ├── types/
│   │   │   └── ui/
│   │   ├── store/
│   │   │   ├── auth.store.test.ts              # Тесты Zustand store (7 тестов)
│   │   │   └── auth.store.ts                   # Zustand: аутентификация, пользователь
│   │   ├── test/
│   │   │   └── setup.ts                        # Vitest setup (happy-dom)
│   │   ├── index.css                           # Глобальные стили + CSS переменные
│   │   ├── main.tsx                            # Точка входа React
│   │   └── vite-env.d.ts                       # Vite типы
│   ├── components.json                         # shadcn/ui конфигурация
│   ├── package.json                            # Зависимости и скрипты
│   ├── tailwind.config.js                      # Tailwind конфигурация
│   ├── tsconfig.json                           # TypeScript конфигурация
│   └── vite.config.ts                          # Vite конфигурация
├── k8s/                                        # Kubernetes манифесты
│   └── base/                                   # Базовые манифесты
│       ├── backend.yml                         # Deployment + Service (backend)
│       ├── configmap.yml                       # Несекретные переменные
│       ├── frontend.yml                        # Deployment + Service (frontend)
│       ├── hpa.yml                             # HorizontalPodAutoscaler (backend, 2–10)
│       ├── ingress.yml                         # Ingress (SSL, маршрутизация)
│       ├── namespace.yml                       # Namespace (omnichannel)
│       ├── network-policy.yml                  # NetworkPolicy (ingress/egress)
│       └── pdb.yml                             # PodDisruptionBudget (minAvailable=1)
├── scripts/                                    # Утилитные скрипты
│   ├── backup-cleanup.sh                       # Очистка старых бэкапов (MinIO)
│   ├── backup.sh                               # Создание бэкапов (PG, Qdrant, Neo4j)
│   └── init-db.sh                              # Инициализация БД (индексы, констрейнты)
├── .env.example                                # Шаблон переменных окружения
├── .gitignore                                  # Git игнорирование
├── docker-compose.yml                          # Docker Compose (все сервисы)
├── Dockerfile.backend                          # Backend (dev)
├── Dockerfile.backend.prod                     # Backend (production, multi-stage)
├── Dockerfile.frontend                         # Frontend (dev)
├── Dockerfile.frontend.prod                    # Frontend (production, multi-stage)
├── nginx.conf                                  # Nginx dev конфиг
├── nginx.prod.conf                             # Nginx production конфиг (SPA)
├── nginx.reverse-proxy.conf                    # Nginx reverse-proxy с SSL
└── README.md                                   # Общее описание проекта
```

---

## 3. Статистика

| Категория | Количество |
|-----------|------------|
| Всего файлов | ~260+ |
| Backend Python файлы | ~80 |
| Frontend файлы (TS/TSX) | ~50 |
| Конфигурационные файлы | ~30 |
| Тесты (unit, integration, e2e) | ~45 |
| Документация (MD) | ~30 |
| Kubernetes манифесты | ~10 |
| Скрипты | ~6 |

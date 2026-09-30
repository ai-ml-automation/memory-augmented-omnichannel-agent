# 📋 IMPLEMENTATION_PLAN.md

## 1. Введение

### 1.1. Цель документа

Настоящий документ представляет собой **единый актуальный план разработки** проекта «Омниканальный агент с долговременной памятью» (Memory-Augmented Omnichannel Agent). Он объединяет все этапы разработки — от инициализации до готовности к пилотному запуску.

Документ предназначен для команды разработки, проектного менеджера и архитектора. Он даёт полное представление о том, что уже сделано, что находится в работе и какие задачи предстоит решить для достижения production‑готовности.

### 1.2. Принципы выполнения

Все работы ведутся в строгом соответствии с источниками правды проекта:

- **[SPEC.md](SPEC.md)** — бизнес-требования, функциональность, РФ-специфика.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — архитектура, компоненты, ADR, потоки данных.
- **[AGENT_WORKFLOW.md](AGENT_WORKFLOW.md)** — регламент работы Build Agent.

Ключевые принципы, которыми руководствуется команда:

- **KISS** — минимум сложности, только необходимая функциональность.
- **YAGNI** — никакого кода «на будущее».
- **Production‑first** — сразу используем реальные БД, очереди, кэш.
- **Монолит на первом этапе** —  всё в одном FastAPI приложении, без микросервисов.
- **Async везде** — все I/O операции неблокирующие.
- **Feature Flags** — тяжёлые сервисы (LLM, ASR, TTS, Memory) управляются флагами и по умолчанию выключены.
- **Lazy Initialization** — модели загружаются только при первом вызове.

### 1.3. Ссылки на источники

| Документ | Описание |
|----------|----------|
| [SPEC.md](SPEC.md) | Полные бизнес-требования и метрики успеха |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектурное описание, ADR, схемы |
| [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) | Регламент работы Build Agent |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Дерево проекта с описанием файлов |

---

## 2. Обзор этапов разработки

В таблице ниже представлены все фазы разработки, их статус и ключевые результаты.

| Фаза | Название | Статус | Ключевые результаты |
|------|----------|--------|---------------------|
| **0** | Инфраструктура и скелет | ✅ Выполнена | Docker‑compose, FastAPI, React, CI, E2E health |
| **1** | Аутентификация и согласие | ✅ Выполнена | AuthService, ConsentService, JWT, фронтенд, E2E |
| **2** | Омниканальный шлюз | ✅ Выполнена | MAX/Telegram/VK интеграции, маршрутизация, сессии, аудит |
| **3** | Memory Layer и извлечение фактов | ✅ Выполнена | FactService, VectorStore, GraphService, LangGraph, Celery |
| **4** | Генерация ответа и UI оператора | ✅ Выполнена | ResponseGenerator, LLMService, PromptBuilder, операторские страницы |
| **5** | Голосовой пайплайн | ✅ Выполнена | Whisper ASR, Silero TTS, VoiceService, WebSocket |
| **6** | Фоновые задачи, Decay, анонимизация | ✅ Выполнена | DecayAgent, шифрование, Presidio, логирование, трассировка |
| **7** | Production Hardening | ✅ Выполнена | Phase A‑G: Auth fixes, CI, Security, Memory abstraction, Embeddings, Testing, Monitoring, Frontend improvements (см. раздел 3) |
| **8** | Доводка до Production‑Ready | ✅ Выполнена | Alembic, CI/CD, Cross‑Encoder preload, технический долг, тесты, Vault, Neo4j backup |
| **Post‑Review** | Доработки по результатам ревью | ⚠️ В процессе | Безопасность, отказоустойчивость, масштабирование, мониторинг, тестирование, документация |

---

## 3. Детальный план по фазам

### 3.1. Фаза 0. Инфраструктура и скелет (неделя 1) — ✅ ВЫПОЛНЕНА

**Цель:** Поднять локальную среду разработки, настроить все базы данных и очереди, создать базовые каркасы бэкенда и фронтенда, настроить CI/CD и линтеры.

#### Раунд 0.1. Настройка окружения и Docker‑композа
- Создан `docker-compose.yml` с PostgreSQL 16, Redis 7.2, Qdrant, Neo4j 5.x, MinIO.
- Настроен `.env.example` с Feature Flags (`ENABLE_LLM=false`, `ENABLE_VOICE=false`, `ENABLE_ASR=false`, `ENABLE_TTS=false`, `ENABLE_MEMORY=false`) и параметрами подключения.
- Написан скрипт [scripts/init-db.sh](../scripts/init-db.sh) для инициализации БД.

#### Раунд 0.2. Создание скелета приложений
- FastAPI проект: [backend/src/main.py](../backend/src/main.py), [backend/src/config.py](../backend/src/config.py), [backend/src/database.py](../backend/src/database.py), [backend/src/models.py](../backend/src/models.py), [backend/src/schemas.py](../backend/src/schemas.py).
- API: эндпоинт `/health` в [backend/src/api/health.py](../backend/src/api/health.py).
- React приложение: [frontend/package.json](../frontend/package.json), базовая структура.
- CI/CD: `.github/workflows/ci.yml` (линтеры, сборка).

#### Раунд 0.3. Документация и начальные тесты
- `README.md` с инструкцией по запуску.
- E2E‑тест для `/health` ([backend/tests/e2e/test_health.py](../backend/tests/e2e/test_health.py)).

**Критерий готовности:**
- ✅ `docker-compose up -d` поднимает все сервисы.
- ✅ FastAPI отвечает на `/health` (200 OK).
- ✅ Фронтенд рендерится.
- ✅ Линтеры проходят.

---

### 3.2. Фаза 1. Аутентификация и согласие (неделя 2) — ✅ ВЫПОЛНЕНА

**Цель:** Реализовать регистрацию/логин, JWT, управление согласием на обработку ПДн (152‑ФЗ). Без согласия память не пишется.

#### Раунд 1.1. Модели и сервисы авторизации
- Модели: `User`, `Consent`, `ChannelBinding` в [backend/src/models.py](../backend/src/models.py).
- `AuthService` ([backend/src/services/auth_service.py](../backend/src/services/auth_service.py)): регистрация (bcrypt), логин (JWT), получение текущего пользователя.
- `ConsentService` ([backend/src/services/consent_service.py](../backend/src/services/consent_service.py)): выдача, отзыв, проверка статуса согласия.

#### Раунд 1.2. API‑эндпоинты и Middleware
- Auth Router ([backend/src/api/auth.py](../backend/src/api/auth.py)): `/register`, `/login`, `/logout`, `/me`.
- Consents Router ([backend/src/api/consents.py](../backend/src/api/consents.py)): `/grant`, `/revoke`, `/status`.
- JWT Middleware ([backend/src/middleware.py](../backend/src/middleware.py)) для автоматической проверки токена.

#### Раунд 1.3. Фронтенд и E2E‑тесты
- React: `App.tsx`, `LoginPage`, `RegisterPage`, `DashboardPage`.
- Auth Store (Zustand): [frontend/src/store/auth.store.ts](../frontend/src/store/auth.store.ts).
- Axios с перехватчиками: [frontend/src/api/axios.ts](../frontend/src/api/axios.ts).
- Consent UI: выдача/отзыв согласия.
- E2E‑тесты: регистрация, логин, /me, logout, consents (9 тестов) в [backend/tests/e2e/test_auth.py](../backend/tests/e2e/test_auth.py).

**Критерий готовности:**
- ✅ Регистрация и логин работают.
- ✅ JWT хранится в httpOnly cookie.
- ✅ Без активного согласия операции с памятью блокируются.
- ✅ E2E‑тесты проходят.

---

### 3.3. Фаза 2. Омниканальный шлюз и сущности (недели 3–4) — ✅ ВЫПОЛНЕНА

**Цель:** Научить систему принимать сообщения из MAX, Telegram, VK и привязывать их к единому `user_id`. Создать модели сессий, фактов и аудита.

#### Раунд 2.1. Модели сессий, фактов и аудита
- Добавлены модели: `Session`, `Fact`, `AuditLog` в [backend/src/models.py](../backend/src/models.py).

#### Раунд 2.2. Интеграции с мессенджерами
- `MAXGateway` ([backend/src/integrations/max_gateway.py](../backend/src/integrations/max_gateway.py)).
- `TelegramGateway` ([backend/src/integrations/telegram_gateway.py](../backend/src/integrations/telegram_gateway.py)).
- `VKGateway` ([backend/src/integrations/vk_gateway.py](../backend/src/integrations/vk_gateway.py)).
- Webhooks Router ([backend/src/api/webhooks.py](../backend/src/api/webhooks.py)): `/webhook/max`, `/webhook/telegram`, `/webhook/vk`, `/webhook/unified`.

#### Раунд 2.3. Сервис идентификации и маршрутизации
- `ChannelBindingService` ([backend/src/services/channel_binding_service.py](../backend/src/services/channel_binding_service.py)).
- `MessageRouter` ([backend/src/services/message_router.py](../backend/src/services/message_router.py)).
- `MessageHandler` ([backend/src/services/message_handler.py](../backend/src/services/message_handler.py)) с проверкой consent и аудитом.

#### Раунд 2.4. Фронтенд: дашборд оператора (базовый)
- Admin Users API ([backend/src/api/admin_users.py](../backend/src/api/admin_users.py)).
- Admin Channels API ([backend/src/api/admin_channels.py](../backend/src/api/admin_channels.py)).
- Operator Dashboard (`frontend/src/pages/operator/`), Users Page, Channels Page.

**Критерий готовности:**
- ✅ Сообщения из MAX, Telegram и VK принимаются и привязываются к пользователю.
- ✅ В БД появляются записи сессий.
- ✅ Фронтенд показывает список активных сессий.

---

### 3.4. Фаза 3. Memory Layer и извлечение фактов (недели 5–6) — ✅ ВЫПОЛНЕНА

**Цель:** Реализовать ядро памяти: извлечение фактов, сохранение в Qdrant и Neo4j, семантический и графовый поиск, разрешение конфликтов.

#### Раунд 3.1. Настройка клиентов памяти (Lazy Initialization)
- Реализованы клиенты Qdrant, Neo4j с ленивой инициализацией.

#### Раунд 3.2. FactExtractor (LangGraph)
- `FactExtractorAgent` ([backend/src/agents/fact_extractor.py](../backend/src/agents/fact_extractor.py)): LLM‑извлечение, фильтрация эмоций, анонимизация PII.
- Интеграция с Celery (`extract_facts_task`).

#### Раунд 3.3. MemoryManager и ConflictResolver
- `MemoryManagerAgent` ([backend/src/agents/memory_manager.py](../backend/src/agents/memory_manager.py)): запись в Qdrant, Neo4j, PostgreSQL, гибридный поиск.
- `ConflictResolverAgent` ([backend/src/agents/conflict_resolver.py](../backend/src/agents/conflict_resolver.py)): правило «позднее перекрывает раннее», HITL.

#### Раунд 3.4. Интеграция в основной пайплайн
- Вебхуки дополнены: асинхронный запуск `extract_facts_task`, синхронный поиск памяти.
- Интеграционные тесты (запись фактов, поиск).

**Критерий готовности:**
- ✅ Сообщение → извлечение фактов → сохранение в память.
- ✅ Поиск возвращает релевантные факты.
- ✅ Конфликты разрешаются.

---

### 3.5. Фаза 4. Генерация ответа и UI оператора (недели 7–8) — ✅ ВЫПОЛНЕНА

**Цель:** Формировать персонализированные ответы с использованием памяти, дать операторам контроль над памятью.

#### Раунд 4.1. ResponseGenerator (LangGraph)
- `ResponseGeneratorAgent` ([backend/src/agents/response_generator.py](../backend/src/agents/response_generator.py)): build_prompt → LLM → fallback.

#### Раунд 4.2. Сервис «Право на забвение»
- `RightToBeForgottenService` ([backend/src/services/right_to_be_forgotten_service.py](../backend/src/services/right_to_be_forgotten_service.py)): каскадное удаление из Qdrant, Neo4j, PostgreSQL, MinIO.
- API: `/consents/data-deletion`.

#### Раунд 4.3. Фронтенд: просмотр памяти и аудит
- Страницы: `MemoryViewPage` ([frontend/src/pages/memory/index.tsx](../frontend/src/pages/memory/index.tsx)), `AuditLogPage` ([frontend/src/pages/audit/index.tsx](../frontend/src/pages/audit/index.tsx)).

#### Раунд 4.4. E2E‑тесты для сценариев с памятью
- E2E‑тесты: извлечение факта, использование памяти, удаление, аудит.

**Критерий готовности:**
- ✅ Агент отвечает, используя факты.
- ✅ Оператор видит память и может удалять.
- ✅ Аудит ведётся.

---

### 3.6. Фаза 5. Голосовой пайплайн и CTI (недели 9–10) — ✅ ВЫПОЛНЕНА

**Цель:** Интегрировать телефонию, ASR и TTS с Lazy Initialization.

#### Раунд 5.1. Интеграция с CTI и обработка звонков
- `VoiceGateway` ([backend/src/integrations/voice_gateway.py](../backend/src/integrations/voice_gateway.py)).

#### Раунд 5.2. ASR и TTS с Lazy Initialization
- `WhisperASR` ([backend/src/services/whisper_asr.py](../backend/src/services/whisper_asr.py)).
- `SileroTTS` ([backend/src/services/silero_tts.py](../backend/src/services/silero_tts.py)).

#### Раунд 5.3. Голосовой пайплайн в LangGraph
- `VoiceService` ([backend/src/services/voice_service.py](../backend/src/services/voice_service.py)): ASR → Memory → LLM → TTS.
- WebSocket `/voice/stream`.

#### Раунд 5.4. Тестирование и Feature Flags
- Интеграционные тесты голосового пайплайна ([backend/tests/integration/test_voice_integration.py](../backend/tests/integration/test_voice_integration.py)).

**Критерий готовности:**
- ✅ Голосовой пайплайн работает end‑to‑end.
- ✅ Feature Flags управляют включением.

---

### 3.7. Фаза 6. Фоновые задачи, Decay и анонимизация (неделя 11) — ✅ ВЫПОЛНЕНА

**Цель:** Реализовать Memory Decay, анонимизацию, логирование, трассировку.

#### Раунд 6.1. DecayAgent (фоновый)
- `DecayAgent` ([backend/src/tasks/decay_tasks.py](../backend/src/tasks/decay_tasks.py)): постепенное уменьшение веса фактов (×0.99/день), удаление при весе < 0.1.
- Celery Beat — запуск раз в час.

#### Раунд 6.2. Усиление анонимизации и шифрования
- `crypto.py` ([backend/src/utils/crypto.py](../backend/src/utils/crypto.py)): AES‑256‑GCM.
- `presidio_anonymizer.py` ([backend/src/utils/presidio_anonymizer.py](../backend/src/utils/presidio_anonymizer.py)): анонимизация PII.
- Интеграция с FactService.

#### Раунд 6.3. Логирование и трассировка
- Структурированные JSON‑логи ([backend/src/logging_config.py](../backend/src/logging_config.py)).
- OpenTelemetry + Jaeger ([backend/src/tracing.py](../backend/src/tracing.py)).

#### Раунд 6.4. Полировка фронтенда
- Обработка ошибок RFC 7807.
- Адаптивная вёрстка.

**Критерий готовности:**
- ✅ Факты теряют вес и удаляются.
- ✅ ПДн не хранятся в открытом виде.
- ✅ Логи структурированы и содержат трассировку.

---

### 3.8. Фаза 7. Production Hardening (неделя 12) — ✅ ВЫПОЛНЕНА

**Цель:** Усилить безопасность, добавить мониторинг, подготовить к деплою.

#### Раунд A.1. Аутентификация и модели
- Добавлено поле `password_hash` в `User`.
- AuthService.register: bcrypt хэширование пароля.
- AuthService.login: проверка пароля через bcrypt.
- Замена bcrypt на HMAC‑SHA256 для хэширования телефона.
- Синхронизация модели Fact (type/value/weight).
- Добавлены настройки в `config.py` (Qdrant, Neo4j, Celery, CORS).

#### Раунд A.2. CI и инфраструктура
- Исправлена опечатка `ubuntu-lcdl` → `ubuntu-latest`.
- Добавлены Prometheus/Grafana/Loki в `docker-compose.yml` (profile: monitoring).
- Health‑эндпоинт проверяет PostgreSQL, Redis, Qdrant, Neo4j.
- CI workflow поднимает Qdrant и Neo4j для интеграционных тестов.

#### Раунд B.1. Шифрование и анонимизация (152‑ФЗ)
- AES‑256‑GCM ([backend/src/utils/crypto.py](../backend/src/utils/crypto.py)).
- Presidio ([backend/src/utils/presidio_anonymizer.py](../backend/src/utils/presidio_anonymizer.py)).
- Проверка согласия во всех операциях с памятью.

#### Раунд B.2. Защита вебхуков и CSRF
- Telegram: `X-Telegram-Bot-Api-Secret-Token`.
- VK: проверка `secret`.
- SameSite=Strict для JWT cookie, CSRF double‑submit.
- CORS ограничен в production.

#### Раунд B.3. Право на забвение и аудит
- `RightToBeForgottenService` ([backend/src/services/right_to_be_forgotten_service.py](../backend/src/services/right_to_be_forgotten_service.py)).
- API `/consents/data-deletion`.
- Аудит всех операций с памятью (READ, WRITE, DELETE).

#### Раунд C.1. Абстракция Memory Layer
- `MemoryService` (ABC) ([backend/src/services/memory_service.py](../backend/src/services/memory_service.py)).
- `Mem0MemoryService` ([backend/src/services/mem0_memory_service.py](../backend/src/services/mem0_memory_service.py)) с graceful degradation.

#### Раунд C.2. Очереди (Celery + Redis)
- `celery_app.py` ([backend/src/celery_app.py](../backend/src/celery_app.py)).
- Задачи: `process_message`, `extract_facts`, `decay_agent`.
- Webhooks диспатчат задачи асинхронно.

#### Раунд C.3. Рефакторинг роутеров и сервисов
- `ChatService` ([backend/src/services/chat_service.py](../backend/src/services/chat_service.py)).
- `VoiceService` ([backend/src/services/voice_service.py](../backend/src/services/voice_service.py)).
- Роутеры стали тонкими.

#### Раунд D.1. Эмбеддинги и Vector Store
- Sentence‑Transformers (`paraphrase-multilingual-MiniLM-L12-v2`).
- Lazy initialization, выделенный ThreadPoolExecutor (16 воркеров).

#### Раунд D.2. Агенты LangGraph
- 4 агента: FactExtractor, MemoryManager, ResponseGenerator, ConflictResolver.

#### Раунд D.3. Голосовой пайплайн
- Whisper ASR, Silero TTS.
- WebSocket `/voice/stream`.

#### Раунд E.1. E2E‑тесты (15)
- Auth (7), Chat (4), Consents (3), Health (1).

#### Раунд E.2. Интеграционные тесты (10)
- Vector Store (1/4 pass, 3 fail — исправлено в Omega), Encryption (3), Celery (4).

#### Раунд E.3. Контрактные тесты (4)
- Webhook payload structures.

#### Раунд E.4. Нагрузочные тесты
- Locust скрипт ([backend/tests/load/locustfile.py](../backend/tests/load/locustfile.py)).

#### Раунд F.1. Мониторинг (Prometheus + Grafana)
- Метрики: `LLM_REQUEST_DURATION`, `QDRANT_SEARCH_DURATION`, `FACTS_EXTRACTED_TOTAL`, `CONFLICTS_DETECTED_TOTAL`, `MEMORY_STORE_DURATION`.
- Дашборды: `omnichannel-backend.json`, `business.json`.
- Алерты: 6 правил (`prometheus-rules.json`).

#### Раунд F.2. Логирование и трассировка
- Структурированные JSON‑логи ([backend/src/logging_config.py](../backend/src/logging_config.py)).
- OpenTelemetry + Jaeger ([backend/src/tracing.py](../backend/src/tracing.py)).

#### Раунд F.3. Бэкапы и восстановление
- [scripts/backup.sh](../scripts/backup.sh) (PostgreSQL, Qdrant snapshot, Neo4j APOC).
- [scripts/backup-cleanup.sh](../scripts/backup-cleanup.sh).
- `docs/RECOVERY.md`.

#### Раунд F.4. Production-деплой
- `Dockerfile.backend.prod`, `Dockerfile.frontend.prod`.
- K8s манифесты: [k8s/base/*.yml](../k8s/base/*.yml).
- Nginx reverse‑proxy (`nginx.reverse-proxy.conf`).

#### Раунд G.1. Формы и валидация (фронтенд)
- `react-hook-form` + `zod` ([frontend/src/lib/validations.ts](../frontend/src/lib/validations.ts)).

#### Раунд G.2. Обработка ошибок и AbortController
- Axios interceptor, `react-hot-toast`.
- `createAbortController` в [frontend/src/api/axios.ts](../frontend/src/api/axios.ts).

#### Раунд G.3. UI/UX и адаптивность
- Responsive Layout с sidebar ([frontend/src/components/Layout.tsx](../frontend/src/components/Layout.tsx)).

#### Раунд G.4. Фронтенд-тесты
- Vitest + testing‑library.
- 22 теста (validations, auth store, layout).

#### Раунд F.1–F.8. Фронтенд-страницы
- Profile, SessionDetail, Sessions, Audit, Memory, Forget, AdminSettings, VoiceTest.

---

### 3.9. Фаза Omega (α–ζ). Доводка до Production‑Ready — ✅ ВЫПОЛНЕНА

**Цель:** Улучшить качество. Доводка до Production‑Ready.

#### Раунд α.1. Alembic (управление схемой БД)
- Инициализирован Alembic (`backend/alembic/`).
- Создана первая миграция (`001_initial_schema.py`).
- Удалён `create_all()` из `main.py` — теперь таблицы создаются только через миграции.

#### Раунд β.1. CI/CD + Secretscan
- Создан `.github/workflows/ci.yml` с линтерами, тестами (на реальном PostgreSQL), сборкой образов.
- Создан `.secretscanignore` для обхода ложных срабатываний.

#### Раунд β.1. Устранение холодного старта Cross‑Encoder
- Предзагрузка Cross‑Encoder (`BAAI/bge-reranker-large`) при старте приложения (`ENABLE_LLM=true`).
- `_get_ranker()` теперь async, использует `run_in_executor`.
- Первый запрос < 500 мс (вместо 5–15 с).

#### Раунд γ.1. Удаление мёртвого поля `encrypted_data`
- Создана миграция `002_remove_encrypted_data.py`.
- Поле удалено из модели `Fact`.

#### Раунд γ.2. DI для MemoryManagerAgent
- `MemoryManagerAgent` теперь принимает `MemoryService` через конструктор (DI).
- Устранено дублирование логики.

#### Раунд δ.1. Генерация аудио-фикстуры `test.wav`
- Создан [backend/tests/fixtures/audio/generate_audio.py](../backend/tests/fixtures/audio/generate_audio.py) (440Hz, 2s, 16kHz).
- Генерируется автоматически при отсутствии.

#### Раунд δ.2. Исправление интеграционных тестов Vector Store
- Использован `patch.dict(sys.modules, fake_modules)` для мокирования `sentence_transformers` и `qdrant_client`.
- Все 4 теста проходят.

#### Раунд ε.1. Бэкап Neo4j через APOC
- [scripts/backup.sh](../scripts/backup.sh) теперь экспортирует Neo4j через APOC JSON.

#### Раунд ζ.1. Интеграция HashiCorp Vault
- `vault_client.py` ([backend/src/vault_client.py](../backend/src/vault_client.py)).
- `config.py`: `effective_jwt_secret`, `effective_encryption_key`.
- JWT и шифрование используют Vault в production, .env в dev.

---

### 3.10. Фаза Post‑Review. Доработки по результатам ревью — ⚠️ В ПРОЦЕССЕ

**Цель:** Устранить критические и важные проблемы, выявленные в ходе всестороннего ревью проекта.

#### Фаза I. Безопасность (в процессе)

**Раунд I.1. Включение CSRF по умолчанию**
- Сделать CSRF проверку всегда включённой, кроме явного флага `ENABLE_CSRF_SKIP=true`.
- **Файл:** [backend/src/api/auth.py](../backend/src/api/auth.py).

**Раунд I.2. Rate limiting**
- Добавить глобальное ограничение запросов через `slowapi`.
- Лимиты: `/login` — 5/мин, остальные — 100/мин.
- **Новый файл:** [backend/src/middleware/rate_limit.py](../backend/src/middleware/rate_limit.py).

**Раунд I.3. Валидация загружаемых файлов (голос)**
- Проверка размера (≤ 10 МБ) и MIME‑типа (`audio/wav`, `audio/mpeg`, `audio/webm`, `audio/ogg`).
- **Файл:** [backend/src/api/voice.py](../backend/src/api/voice.py).

**Раунд I.4. Защита от брутфорса (логин)**
- Отслеживание неудачных попыток (5 попыток за 5 минут).
- **Новый файл:** [backend/src/services/bruteforce_service.py](../backend/src/services/bruteforce_service.py).

#### Фаза II. Отказоустойчивость (запланирована)

**Раунд II.1. Circuit Breaker + Retry**
- Использовать `tenacity` для повторных попыток, `circuitbreaker` для защиты внешних сервисов (LLM, Qdrant, Neo4j).
- **Новый файл:** [backend/src/utils/resilience.py](../backend/src/utils/resilience.py).

**Раунд II.2. Централизованный HTTP‑клиент с таймаутами**
- Единая фабрика `get_async_client()` с конфигурируемыми таймаутами.
- **Новый файл:** [backend/src/utils/http_client.py](../backend/src/utils/http_client.py).

**Раунд II.3. Graceful Shutdown**
- Убедиться, что при остановке приложения закрываются все соединения (БД, Redis, Qdrant, Neo4j).
- **Файл:** [backend/src/main.py](../backend/src/main.py) (lifespan).

#### Фаза III. Масштабирование (запланирована)

**Раунд III.1. HPA для Celery (по длине очереди)**
- Настроить экспорт метрики длины очереди и HPA для celery‑воркеров.
- **Файлы:** [k8s/base/hpa.yml](../k8s/base/hpa.yml), новый экспортёр метрик.

**Раунд III.2. Масштабирование Mem0**
- Документировать текущее состояние (один инстанс) и план масштабирования.
- **Файл:** [ARCHITECTURE.md](ARCHITECTURE.md) (обновить).

**Раунд III.3. Версионирование API**
- Добавить префикс `/api/v1` ко всем роутерам (кроме `/health`, `/metrics`).
- **Файл:** [backend/src/main.py](../backend/src/main.py), обновить фронтенд `baseURL`.

**Раунд III.4. Персистентность чекпоинтов LangGraph (Redis AOF)**
- Включить AOF в Redis для сохранения состояния при перезапуске.
- **Файл:** [docker-compose.yml](../docker-compose.yml).

#### Фаза IV. Мониторинг и наблюдаемость (запланирована)

**Раунд IV.1. Проброс trace_id/user_id в логи**
- Создать ContextVar и middleware для проброса `trace_id`, `user_id` в логи.
- **Новый файл:** [backend/src/middleware/tracing.py](../backend/src/middleware/tracing.py).

**Раунд IV.2. Бизнес‑метрики**
- Добавить метрики: доля диалогов с памятью, повторные обращения, AHT.
- **Файл:** [backend/src/metrics.py](../backend/src/metrics.py).

**Раунд IV.3. Алерты**
- Дополнить [config/prometheus-rules.json](../config/prometheus-rules.json) алертами на высокую задержку LLM, падение Qdrant, высокий процент ошибок 5xx.

#### Фаза V. Тестирование (запланирована)

**Раунд V.1. Исправление интеграционных тестов Vector Store**
- Использовать `patch.dict(sys.modules, fake_modules)` (уже сделано в Omega ε.2).

**Раунд V.2. Нагрузочное тестирование (Locust)**
- Запустить Locust на 100 пользователях, замерить p95, задокументировать в [docs/PERFORMANCE_REPORT.md](../docs/PERFORMANCE_REPORT.md).

**Раунд V.3. Контрактные тесты для LLM (JSON‑схема)**
- Добавить тесты, проверяющие, что LLM возвращает валидный JSON по схеме.
- **Новый файл:** [backend/tests/unit/test_llm_schema.py](../backend/tests/unit/test_llm_schema.py).

---

## 4. Оценка трудозатрат для оставшихся работ (Post‑Review)

| Фаза | Раунды | Человеко‑дни |
|------|--------|--------------|
| **I. Безопасность** | I.1–I.4 | 3 |
| **II. Отказоустойчивость** | II.1–II.3 | 2 |
| **III. Масштабирование** | III.1–III.4 | 2 |
| **IV. Мониторинг** | IV.1–IV.3 | 2 |
| **V. Тестирование** | V.1–V.3 | 3 |
| **Итого** | | **12** |
| **Буфер (20%)** | | **3** |
| **Всего** | | **~15** |

---

## 5. Чек‑лист готовности к пилоту

- [ ] Все модульные, интеграционные, E2E и контрактные тесты проходят.
- [ ] Нагрузочные тесты подтверждают целевые метрики (p95 < 300 мс для поиска, < 3 с для LLM).
- [ ] CSRF включён, rate limiting настроен, брутфорс‑защита работает.
- [ ] Circuit Breaker и Retry внедрены для LLM, Qdrant, Neo4j.
- [ ] HPA для Celery настроен и протестирован.
- [ ] API версионирован (`/api/v1`).
- [ ] Бизнес‑метрики отображаются в Grafana, алерты настроены.
- [ ] Бэкапы (PostgreSQL, Qdrant, Neo4j) создаются и проверены.
- [ ] Документация обновлена (ARCHITECTURE, RUNBOOK, OPERATOR_GUIDE).
- [ ] Команда обучена работе с системой и реагированию на инциденты.
- [ ] План отката готов.

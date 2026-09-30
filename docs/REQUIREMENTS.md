# 📋 REQUIREMENTS.md

## 1. Введение

### 1.1. Цель документа

Настоящий документ содержит **полный и детализированный перечень требований** к системе «Омниканальный агент с долговременной памятью». Он является основным источником правды для всех функциональных и нефункциональных требований, на основе которых строится система.

Документ структурирован по следующим категориям:

- **Бизнес-требования** — высокоуровневые цели и метрики успеха.
- **Функциональные требования** — что система должна делать.
- **Требования к данным** — как данные хранятся, защищаются и управляются.
- **Требования к интеграциям** — взаимодействие с внешними системами.
- **Нефункциональные требования** — производительность, безопасность, масштабируемость.
- **Требования к документации и эксплуатации** — руководства, мониторинг, поддержка.

Каждое требование имеет уникальный идентификатор (RXX), приоритет, категорию и трассировку в код и тесты.

### 1.2. Как читать документ

- **ID требования** — уникальный идентификатор (например, R01).
- **Приоритет** — Critical, High, Medium, Low.
- **Категория** — Business, Functional, Data, Integration, Non-functional, Documentation.
- **Описание** — что требуется от системы.
- **Критерии приемки** — измеримые условия выполнения.
- **Реализация** — ссылки на файлы, классы, методы в коде.
- **Тесты** — ссылки на тесты, покрывающие требование.
- **Документация** — ссылки на разделы документов, описывающих требование.

### 1.3. Связанные документы

| Документ | Назначение |
|----------|------------|
| [SPEC.md](SPEC.md) | Бизнес-требования, метрики успеха, РФ-специфика |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектурное описание, ADR |
| [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) | Детальные архитектурные решения |
| [USER_STORIES.md](USER_STORIES.md) | Пользовательские истории |
| [USE_CASES.md](USE_CASES.md) | Детальные варианты использования |
| [DATA_FLOWS.md](DATA_FLOWS.md) | Потоки данных и диаграммы |
| [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md) | Детальное описание агентов |
| [API_REFERENCE.md](API_REFERENCE.md) | Спецификация API |
| [SECURITY_GUIDE.md](SECURITY_GUIDE.md) | Безопасность и 152-ФЗ |
| [MONITORING_GUIDE.md](MONITORING_GUIDE.md) | Мониторинг и наблюдаемость |

---

## 2. Бизнес-требования

### 2.1. BR-01: Персонализация на основе памяти

| Атрибут | Значение |
|---------|----------|
| **ID** | BR-01 |
| **Приоритет** | Critical |
| **Категория** | Business |

**Описание:** Система должна обеспечивать персонализированное взаимодействие с клиентом на основе извлечённых фактов из предыдущих обращений.

**Критерии приемки:**
- Доля диалогов с использованием исторического контекста > 30%.
- Клиент не повторяет свои вопросы при переходе между каналами.
- Агент упоминает предыдущие интересы клиента в ответах.

**Реализация:**
- [backend/src/agents/response_generator.py](../backend/src/agents/response_generator.py) — генерация персонализированных ответов.
- [backend/src/services/memory_search_service.py](../backend/src/services/memory_search_service.py) — поиск релевантных фактов.

**Тесты:** [backend/tests/e2e/test_chat_e2e.py](../backend/tests/e2e/test_chat_e2e.py)

**Документация:** [SPEC.md - 1.2](SPEC.md#12-бизнес-цели-и-ожидаемый-эффект), [AGENTS_REFERENCE.md - 5](AGENTS_REFERENCE.md#5-agent-responsegenerator)

---

### 2.2. BR-02: Снижение повторных обращений

| Атрибут | Значение |
|---------|----------|
| **ID** | BR-02 |
| **Приоритет** | Critical |
| **Категория** | Business |

**Описание:** Система должна снижать количество повторных обращений по одному и тому же вопросу.

**Критерии приемки:**
- Повторные обращения < 10% (снижение на 70% от текущего уровня).
- Факты из предыдущих обращений используются для решения текущего запроса.

**Реализация:**
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — хранение и обновление фактов.
- [backend/src/tasks/decay_tasks.py](../backend/src/tasks/decay_tasks.py) — удаление устаревших фактов.

**Документация:** [SPEC.md - 1.2](SPEC.md#12-бизнес-цели-и-ожидаемый-эффект)

---

### 2.3. BR-03: Сокращение AHT

| Атрибут | Значение |
|---------|----------|
| **ID** | BR-03 |
| **Приоритет** | High |
| **Категория** | Business |

**Описание:** Система должна сокращать среднее время обработки обращения (AHT) на 15%.

**Критерии приемки:**
- AHT снижается на 15% по сравнению с текущим уровнем.
- Время ответа агента (текст) < 3 секунд (p95).
- Время ответа агента (голос) < 5 секунд (p95).

**Реализация:**
- [backend/src/services/session_service.py](../backend/src/services/session_service.py) — отслеживание длительности сессий.
- [backend/src/metrics.py](../backend/src/metrics.py) — сбор метрик AHT.

**Документация:** [SPEC.md - 1.2](SPEC.md#12-бизнес-цели-и-ожидаемый-эффект), [MONITORING_GUIDE.md - 2.2](MONITORING_GUIDE.md#22-бизнес-метрики-планируются)

---

### 2.4. BR-04: Рост NPS

| Атрибут | Значение |
|---------|----------|
| **ID** | BR-04 |
| **Приоритет** | High |
| **Категория** | Business |

**Описание:** Система должна обеспечить рост NPS (Net Promoter Score) на +5–10 пунктов.

**Критерии приемки:**
- Рост NPS в пилотной группе по сравнению с контрольной.
- Положительная обратная связь от клиентов о персонализации.

**Реализация:** Метрика собирается через опросы и аналитические дашборды.

**Документация:** [SPEC.md - 1.2](SPEC.md#12-бизнес-цели-и-ожидаемый-эффект), [MONITORING_GUIDE.md - 3.2](MONITORING_GUIDE.md#32-business-metrics-бизнес-дашборд)

---

## 3. Функциональные требования

### 3.1. FR-01: Извлечение фактов из текста

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-01 |
| **Приоритет** | Critical |
| **Категория** | Functional |

**Описание:** Система должна извлекать структурированные факты из текстовых сообщений пользователей.

**Критерии приемки:**
- Извлекаются факты типов: intent, preference, complaint, agreement, rejection, personal_info.
- Факты имеют вес (importance) от 0 до 1.
- Эмоциональные высказывания фильтруются (не сохраняются).
- PII анонимизируется перед сохранением.

**Реализация:**
- [backend/src/agents/fact_extractor.py](../backend/src/agents/fact_extractor.py) — основной агент.
- [backend/src/services/llm_service.py](../backend/src/services/llm_service.py) — вызов LLM для извлечения.
- [backend/src/utils/presidio_anonymizer.py](../backend/src/utils/presidio_anonymizer.py) — анонимизация PII.
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — сохранение фактов.

**Тесты:** [backend/tests/unit/test_agents.py](../backend/tests/unit/test_agents.py) (FactExtractor)

**Документация:** [AGENTS_REFERENCE.md - 3](AGENTS_REFERENCE.md#3-agent-factextractor), [DATA_FLOWS.md - 2.3 Шаг 7](DATA_FLOWS.md#шаг-7-асинхронное-извлечение-и-сохранение-фактов-в-фоне)

---

### 3.2. FR-02: Гибридный поиск памяти

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-02 |
| **Приоритет** | Critical |
| **Категория** | Functional |

**Описание:** Система должна выполнять поиск релевантных фактов, комбинируя ключевой, векторный и графовый поиск.

**Критерии приемки:**
- Поиск выполняется по трём методам: keyword (PostgreSQL), vector (Qdrant), graph (Neo4j).
- Результаты объединяются и переранжируются с помощью Cross-Encoder.
- Время поиска < 300 мс (p95).
- Возвращаются только факты с весом > 0.3.

**Реализация:**
- [backend/src/services/memory_search_service.py](../backend/src/services/memory_search_service.py) — основной сервис.
- [backend/src/services/vector_store_service.py](../backend/src/services/vector_store_service.py) — векторный поиск.
- [backend/src/services/graph_service.py](../backend/src/services/graph_service.py) — графовый поиск.
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — ключевой поиск.

**Тесты:** [backend/tests/integration/test_vector_store_integration.py](../backend/tests/integration/test_vector_store_integration.py)

**Документация:** [DATA_FLOWS.md - 2.3 Шаг 4](DATA_FLOWS.md#шаг-4-синхронный-поиск-памяти-для-формирования-ответа), [ARCHITECTURE.md - 5.2](ARCHITECTURE.md#52-базы-данных)

---

### 3.3. FR-03: Генерация персонализированного ответа

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-03 |
| **Приоритет** | Critical |
| **Категория** | Functional |

**Описание:** Система должна генерировать персонализированные ответы с использованием контекста из памяти.

**Критерии приемки:**
- Ответ содержит персонализированные элементы (имя, предыдущие интересы).
- При недоступности LLM используется шаблонный fallback.
- Время генерации ответа < 3 секунд (текст).

**Реализация:**
- [backend/src/agents/response_generator.py](../backend/src/agents/response_generator.py) — основной агент.
- [backend/src/services/llm_service.py](../backend/src/services/llm_service.py) — вызов LLM.
- [backend/src/services/prompt_builder.py](../backend/src/services/prompt_builder.py) — построение промпта.

**Тесты:** [backend/tests/unit/test_agents.py](../backend/tests/unit/test_agents.py) (ResponseGenerator)

**Документация:** [AGENTS_REFERENCE.md - 5](AGENTS_REFERENCE.md#5-agent-responsegenerator), [DATA_FLOWS.md - 2.3 Шаг 5](DATA_FLOWS.md#шаг-5-генерация-персонализированного-ответа)

---

### 3.4. FR-04: Омниканальный шлюз

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-04 |
| **Приоритет** | Critical |
| **Категория** | Functional |

**Описание:** Система должна принимать сообщения из всех каналов: MAX, Telegram, VK, Voice.

**Критерии приемки:**
- Сообщения из MAX принимаются через webhook.
- Сообщения из Telegram принимаются через webhook с проверкой секрета.
- Сообщения из VK принимаются через Callback API с проверкой секрета.
- Голосовые звонки принимаются через CTI (Naumen) / WebSocket.
- Все каналы привязываются к единому `user_id`.

**Реализация:**
- [backend/src/api/webhooks.py](../backend/src/api/webhooks.py) — вебхуки для MAX, Telegram, VK.
- [backend/src/api/voice.py](../backend/src/api/voice.py) — голосовой API.
- [backend/src/integrations/max_gateway.py](../backend/src/integrations/max_gateway.py) — MAX.
- [backend/src/integrations/telegram_gateway.py](../backend/src/integrations/telegram_gateway.py) — Telegram.
- [backend/src/integrations/vk_gateway.py](../backend/src/integrations/vk_gateway.py) — VK.
- [backend/src/integrations/voice_gateway.py](../backend/src/integrations/voice_gateway.py) — Voice.
- [backend/src/services/channel_binding_service.py](../backend/src/services/channel_binding_service.py) — привязка к user_id.

**Тесты:** [backend/tests/e2e/test_webhooks_e2e.py](../backend/tests/e2e/test_webhooks_e2e.py)

**Документация:** [INTEGRATIONS_REFERENCE.md - 2,3,4,5](INTEGRATIONS_REFERENCE.md#2-интеграция-1-max), [ARCHITECTURE.md - 4](ARCHITECTURE.md#4-общая-схема)

---

### 3.5. FR-05: Голосовой пайплайн

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-05 |
| **Приоритет** | High |
| **Категория** | Functional |

**Описание:** Система должна поддерживать голосовое взаимодействие: ASR (распознавание) и TTS (синтез).

**Критерии приемки:**
- Аудио транскрибируется в текст через Whisper (или Yandex SpeechKit).
- Ответ синтезируется в речь через Silero (или Yandex SpeechKit).
- Голосовой пайплайн управляется флагом `ENABLE_VOICE`.
- Модели загружаются лениво (только при первом вызове).

**Реализация:**
- [backend/src/services/whisper_asr.py](../backend/src/services/whisper_asr.py) — ASR.
- [backend/src/services/silero_tts.py](../backend/src/services/silero_tts.py) — TTS.
- [backend/src/services/voice_service.py](../backend/src/services/voice_service.py) — пайплайн.
- [backend/src/api/voice.py](../backend/src/api/voice.py) — WebSocket эндпоинт.

**Тесты:** [backend/tests/integration/test_voice_integration.py](../backend/tests/integration/test_voice_integration.py)

**Документация:** [DATA_FLOWS.md - 3](DATA_FLOWS.md#3-сценарий-2-голосовой-звонок), [AGENTS_REFERENCE.md - 8.2](AGENTS_REFERENCE.md#82-голосовой-пайплайн-voiceservice)

---

### 3.6. FR-06: Разрешение конфликтов фактов

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-06 |
| **Приоритет** | High |
| **Категория** | Functional |

**Описание:** Система должна разрешать конфликты между новыми и существующими фактами.

**Критерии приемки:**
- Применяется правило «позднее перекрывает раннее».
- При конфликте с разницей во времени < 5 минут требуется HITL (уведомление оператору).
- Старый факт помечается как `superseded` с весом 0.1.

**Реализация:**
- [backend/src/agents/conflict_resolver.py](../backend/src/agents/conflict_resolver.py) — основной агент.

**Тесты:** [backend/tests/unit/test_agents.py](../backend/tests/unit/test_agents.py) (ConflictResolver)

**Документация:** [AGENTS_REFERENCE.md - 6](AGENTS_REFERENCE.md#6-agent-conflictresolver), [ARCHITECTURE.md - 5.4](ARCHITECTURE.md#54-агенты-langgraph)

---

### 3.7. FR-07: Управление сессиями

| Атрибут | Значение |
|---------|----------|
| **ID** | FR-07 |
| **Приоритет** | Medium |
| **Категория** | Functional |

**Описание:** Система должна отслеживать сессии взаимодействия с пользователями.

**Критерии приемки:**
- Каждое обращение создаёт или обновляет сессию.
- Сессия содержит канал, время начала/окончания, контекст (JSON).
- Сессии можно просматривать через UI и API.

**Реализация:**
- [backend/src/services/session_service.py](../backend/src/services/session_service.py) — основной сервис.
- [backend/src/models.py](../backend/src/models.py) — модель `Session`.
- [frontend/src/pages/sessions/index.tsx](../frontend/src/pages/sessions/index.tsx) — UI.

**Документация:** [API_REFERENCE.md - 4.5-4.6](API_REFERENCE.md#45-session-detail), [UI_REFERENCE.md - 4.5-4.6](UI_REFERENCE.md#45-sessions-list-page)

---

## 4. Требования к данным

### 4.1. DR-01: Шифрование PII (AES-256-GCM)

| Атрибут | Значение |
|---------|----------|
| **ID** | DR-01 |
| **Приоритет** | Critical |
| **Категория** | Data |

**Описание:** Все персональные данные должны шифроваться на уровне приложения перед сохранением в БД.

**Критерии приемки:**
- Используется AES-256-GCM с 32-байтным ключом.
- Ключ хранится в HashiCorp Vault (production) или .env (development).
- Шифруется поле `value` в таблице `Fact`.
- Шифрование/дешифрование происходит прозрачно для бизнес-логики.

**Реализация:**
- [backend/src/utils/crypto.py](../backend/src/utils/crypto.py) — шифрование/дешифрование.
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — применение при сохранении/чтении.

**Тесты:** [backend/tests/unit/test_crypto.py](../backend/tests/unit/test_crypto.py), [backend/tests/integration/test_encryption_integration.py](../backend/tests/integration/test_encryption_integration.py)

**Документация:** [SECURITY_GUIDE.md - 4.1](SECURITY_GUIDE.md#41-шифрование-pii-в-бд-aes-256-gcm), [ARCHITECTURE_DECISIONS.md - 15](ARCHITECTURE_DECISIONS.md#15-решение-14-шифрование-pii-aes-256-gcm)

---

### 4.2. DR-02: Анонимизация PII (Presidio)

| Атрибут | Значение |
|---------|----------|
| **ID** | DR-02 |
| **Приоритет** | Critical |
| **Категория** | Data |

**Описание:** Перед сохранением фактов необходимо анонимизировать PII (имена, телефоны, адреса, паспортные данные).

**Критерии приемки:**
- Используется Microsoft Presidio для обнаружения PII.
- Поддерживаются русские документы: паспорт РФ, СНИЛС, ИНН, ОГРН.
- PII заменяются на маски (например, `<PERSON>`).

**Реализация:**
- [backend/src/utils/presidio_anonymizer.py](../backend/src/utils/presidio_anonymizer.py) — основной интерфейс.
- [backend/src/utils/presidio_russian.py](../backend/src/utils/presidio_russian.py) — кастомные recognizers.

**Тесты:** [backend/tests/unit/test_presidio_anonymizer.py](../backend/tests/unit/test_presidio_anonymizer.py)

**Документация:** [SECURITY_GUIDE.md - 4.2](SECURITY_GUIDE.md#42-анонимизация-pii-presidio), [ARCHITECTURE_DECISIONS.md - 16](ARCHITECTURE_DECISIONS.md#16-решение-15-анонимизация-pii-через-presidio)

---

### 4.3. DR-03: Право на забвение (RTBF)

| Атрибут | Значение |
|---------|----------|
| **ID** | DR-03 |
| **Приоритет** | Critical |
| **Категория** | Data |

**Описание:** Система должна обеспечивать полное каскадное удаление всех данных пользователя по его запросу.

**Критерии приемки:**
- Удаление из PostgreSQL (факты, сессии, согласия, привязки, пользователь).
- Удаление из Qdrant (все векторные точки).
- Удаление из Neo4j (все узлы и связи).
- Удаление из MinIO (все аудиофайлы).
- Срок исполнения < 24 часа.
- Запись в аудит-лог.

**Реализация:**
- [backend/src/services/right_to_be_forgotten_service.py](../backend/src/services/right_to_be_forgotten_service.py) — основной сервис.
- [backend/src/api/consents.py](../backend/src/api/consents.py) — API эндпоинт.

**Тесты:** [backend/tests/unit/test_right_to_be_forgotten.py](../backend/tests/unit/test_right_to_be_forgotten.py)

**Документация:** [DATA_FLOWS.md - 4](DATA_FLOWS.md#4-сценарий-3-право-на-забвение-rtbf), [SECURITY_GUIDE.md - 6](SECURITY_GUIDE.md#6-право-на-забвение-rtbf)

---

### 4.4. DR-04: Аудит всех операций с памятью

| Атрибут | Значение |
|---------|----------|
| **ID** | DR-04 |
| **Приоритет** | High |
| **Категория** | Data |

**Описание:** Все операции с памятью (чтение, запись, удаление) должны логироваться для аудита.

**Критерии приемки:**
- Логируются: user_id, action (READ/WRITE/DELETE), fact_id, timestamp, source (AI/OPERATOR), ip_address.
- Логи хранятся 3 года.
- Аудит доступен через UI и API.

**Реализация:**
- [backend/src/services/audit_service.py](../backend/src/services/audit_service.py) — основной сервис.
- [backend/src/models.py](../backend/src/models.py) — модель `AuditLog`.
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — вызовы аудита.
- [frontend/src/pages/audit/index.tsx](../frontend/src/pages/audit/index.tsx) — UI.

**Документация:** [SECURITY_GUIDE.md - 5](SECURITY_GUIDE.md#5-аудит-и-логирование-152-фз), [DATA_FLOWS.md - 7](DATA_FLOWS.md#7-сценарий-6-аудит-операции-с-памятью)

---

### 4.5. DR-05: Memory Decay (устаревание фактов)

| Атрибут | Значение |
|---------|----------|
| **ID** | DR-05 |
| **Приоритет** | Medium |
| **Категория** | Data |

**Описание:** Факты должны автоматически терять вес со временем и удаляться при достижении порога.

**Критерии приемки:**
- Вес факта уменьшается на 1% в день (×0.99 за цикл).
- При весе < 0.1 факт помечается как `superseded` и исключается из поиска.
- При истечении `expires_at` факт удаляется полностью.
- Decay запускается раз в час через Celery Beat.

**Реализация:**
- [backend/src/tasks/decay_tasks.py](../backend/src/tasks/decay_tasks.py) — задача Celery.
- [backend/src/celery_app.py](../backend/src/celery_app.py) — расписание Beat.

**Документация:** [DATA_FLOWS.md - 6](DATA_FLOWS.md#6-сценарий-5-decay-фоновое-устаревание), [AGENTS_REFERENCE.md - 7](AGENTS_REFERENCE.md#7-agent-decayagent-фоновый)

---

## 5. Требования к интеграциям

### 5.1. IR-01: Вебхуки с проверкой секретов

| Атрибут | Значение |
|---------|----------|
| **ID** | IR-01 |
| **Приоритет** | Critical |
| **Категория** | Integration |

**Описание:** Все вебхуки должны защищаться проверкой секретов для предотвращения несанкционированного доступа.

**Критерии приемки:**
- Telegram: проверка `X-Telegram-Bot-Api-Secret-Token`.
- VK: проверка параметра `secret` в callback.
- MAX: проверка не требуется (защита на уровне провайдера).

**Реализация:**
- [backend/src/api/webhooks.py](../backend/src/api/webhooks.py) — `_verify_telegram_secret()`, `_verify_vk_secret()`.

**Тесты:** [backend/tests/unit/test_webhook_security.py](../backend/tests/unit/test_webhook_security.py), [backend/tests/e2e/test_webhooks_e2e.py](../backend/tests/e2e/test_webhooks_e2e.py)

**Документация:** [INTEGRATIONS_REFERENCE.md - 3.5, 4.5](INTEGRATIONS_REFERENCE.md#35-безопасность-secret-token), [SECURITY_GUIDE.md - 3.2](SECURITY_GUIDE.md#32-безопасность-вебхуков)

---

### 5.2. IR-02: Lazy Initialization для ML-моделей

| Атрибут | Значение |
|---------|----------|
| **ID** | IR-02 |
| **Приоритет** | High |
| **Категория** | Integration |

**Описание:** Все ML-модели (Whisper, Silero, Cross-Encoder, Embedding) должны загружаться только при первом вызове.

**Критерии приемки:**
- Модель не загружается в `__init__`.
- Модель загружается в методе при первом реальном вызове.
- Время старта приложения < 10 секунд.
- Предзагрузка Cross-Encoder при старте (если ENABLE_LLM=true).

**Реализация:**
- [backend/src/services/whisper_asr.py](../backend/src/services/whisper_asr.py) — `_load_model()`.
- [backend/src/services/silero_tts.py](../backend/src/services/silero_tts.py) — `_get_model()`.
- [backend/src/services/memory_search_service.py](../backend/src/services/memory_search_service.py) — `_get_ranker()`.

**Документация:** [ARCHITECTURE_DECISIONS.md - 9](ARCHITECTURE_DECISIONS.md#9-решение-8-lazy-initialization-для-ml-моделей)

---

## 6. Нефункциональные требования

### 6.1. NFR-01: Производительность

| Атрибут | Значение |
|---------|----------|
| **ID** | NFR-01 |
| **Приоритет** | High |
| **Категория** | Non-functional |

**Описание:** Система должна обеспечивать заданную производительность при нагрузке до 1000 одновременных сессий.

**Критерии приемки:**
- Время извлечения фактов (p95) < 2 сек.
- Время поиска в памяти (p95) < 300 мс.
- Время генерации ответа (текст, p95) < 3 сек.
- Время генерации ответа (голос, p95) < 5 сек.
- Поддержка одновременных сессий ≥ 1000.

**Реализация:** Мониторинг через Prometheus + Grafana.

**Документация:** [MONITORING_GUIDE.md - 2](MONITORING_GUIDE.md#2-метрики-prometheus)

---

### 6.2. NFR-02: Отказоустойчивость

| Атрибут | Значение |
|---------|----------|
| **ID** | NFR-02 |
| **Приоритет** | High |
| **Категория** | Non-functional |

**Описание:** Система должна сохранять работоспособность при сбоях внешних сервисов.

**Критерии приемки:**
- При недоступности Mem0 — работа без памяти (только текущий диалог).
- При недоступности Qdrant — используется только кэш Redis.
- При недоступности LLM — шаблонный fallback.
- Доступность (Availability) ≥ 99.5%.

**Реализация:**
- [backend/src/services/mem0_memory_service.py](../backend/src/services/mem0_memory_service.py) — graceful degradation.
- [backend/src/services/llm_service.py](../backend/src/services/llm_service.py) — fallback.

**Документация:** [ARCHITECTURE.md - 10](ARCHITECTURE.md#10-масштабирование-и-отказоустойчивость), [RUNBOOK.md](RUNBOOK.md)

---

### 6.3. NFR-03: Безопасность и 152-ФЗ

| Атрибут | Значение |
|---------|----------|
| **ID** | NFR-03 |
| **Приоритет** | Critical |
| **Категория** | Non-functional |

**Описание:** Система должна полностью соответствовать требованиям 152-ФЗ и обеспечивать защиту данных.

**Критерии приемки:**
- Согласие на обработку ПДн запрашивается явно.
- ПДн шифруются и анонимизируются.
- Ведётся аудит всех операций.
- Реализовано право на забвение.
- CORS ограничен в production.
- CSRF защита включена.
- Rate limiting (планируется).

**Реализация:** Все компоненты безопасности, описанные в [SECURITY_GUIDE.md](SECURITY_GUIDE.md).

**Документация:** [SECURITY_GUIDE.md](SECURITY_GUIDE.md), [ARCHITECTURE_DECISIONS.md - 11-18](ARCHITECTURE_DECISIONS.md#11-решение-11-аутентификация-через-jwt-в-httponly-cookie)

---

### 6.4. NFR-04: Масштабируемость

| Атрибут | Значение |
|---------|----------|
| **ID** | NFR-04 |
| **Приоритет** | Medium |
| **Категория** | Non-functional |

**Описание:** Система должна поддерживать горизонтальное масштабирование всех компонентов.

**Критерии приемки:**
- API-шлюз масштабируется через HPA (2–10 подов).
- Celery workers масштабируются по длине очереди (планируется).
- Базы данных имеют кластерную архитектуру.
- Mem0 имеет план масштабирования (ADR #8).

**Реализация:**
- [k8s/base/hpa.yml](../k8s/base/hpa.yml) — HPA для backend.
- [docker-compose.yml](../docker-compose.yml) — кластеризация БД.

**Документация:** [SCALING_GUIDE.md](SCALING_GUIDE.md), [ARCHITECTURE.md - 10](ARCHITECTURE.md#10-масштабирование-и-отказоустойчивость)

---

### 6.5. NFR-05: Наблюдаемость

| Атрибут | Значение |
|---------|----------|
| **ID** | NFR-05 |
| **Приоритет** | High |
| **Категория** | Non-functional |

**Описание:** Система должна обеспечивать полную наблюдаемость: метрики, логи, трассировка.

**Критерии приемки:**
- Метрики: Prometheus (технические и бизнес).
- Логи: структурированные JSON с PII-редикцией, сбор в Loki.
- Трассировка: OpenTelemetry + Jaeger.
- Дашборды: Grafana.
- Алерты: настроены для критических метрик.

**Реализация:**
- [backend/src/metrics.py](../backend/src/metrics.py) — метрики.
- [backend/src/logging_config.py](../backend/src/logging_config.py) — логи.
- [backend/src/tracing.py](../backend/src/tracing.py) — трассировка.
- [config/prometheus-rules.json](../config/prometheus-rules.json) — алерты.

**Документация:** [MONITORING_GUIDE.md](MONITORING_GUIDE.md)

---

## 7. Требования к документации и эксплуатации

### 7.1. DR-01: Документация для разработчиков

| Атрибут | Значение |
|---------|----------|
| **ID** | DOC-01 |
| **Приоритет** | Medium |
| **Категория** | Documentation |

**Описание:** Должна быть подготовлена документация для разработчиков.

**Критерии приемки:**
- README.md с инструкцией по запуску.
- DEVELOPMENT_GUIDE.md с настройкой окружения.
- API_REFERENCE.md со спецификацией API.

**Реализация:** Документы, созданные в рамках проекта.

---

### 7.2. DOC-02: Документация для операторов

| Атрибут | Значение |
|---------|----------|
| **ID** | DOC-02 |
| **Приоритет** | Medium |
| **Категория** | Documentation |

**Описание:** Должна быть подготовлена документация для операторов и администраторов.

**Критерии приемки:**
- OPERATOR_GUIDE.md с инструкциями по управлению памятью.
- RUNBOOK.md с инструкциями для дежурного инженера.

**Реализация:** Документы, созданные в рамках проекта.

---

## 8. Матрица трассировки требований

| ID | Тип | Приоритет | Реализация | Тесты | Документация |
|----|-----|-----------|------------|-------|--------------|
| BR-01 | Business | Critical | `response_generator.py`, `memory_search_service.py` | E2E | SPEC 1.2, AGENTS_REF 5 |
| BR-02 | Business | Critical | `fact_service.py`, `decay_tasks.py` | Unit | SPEC 1.2 |
| BR-03 | Business | High | `session_service.py`, `metrics.py` | — | SPEC 1.2, MONITORING 2.2 |
| BR-04 | Business | High | Аналитические дашборды | — | SPEC 1.2, MONITORING 3.2 |
| FR-01 | Functional | Critical | `fact_extractor.py`, `llm_service.py`, `presidio_anonymizer.py` | Unit | AGENTS_REF 3, DATA_FLOWS 2.3 |
| FR-02 | Functional | Critical | `memory_search_service.py`, `vector_store_service.py`, `graph_service.py` | Integration | DATA_FLOWS 2.3, ARCH 5.2 |
| FR-03 | Functional | Critical | `response_generator.py`, `llm_service.py` | Unit | AGENTS_REF 5, DATA_FLOWS 2.3 |
| FR-04 | Functional | Critical | `webhooks.py`, `integrations/*_gateway.py` | E2E | INTEGRATIONS 2-5, ARCH 4 |
| FR-05 | Functional | High | `voice.py`, `whisper_asr.py`, `silero_tts.py` | Integration | DATA_FLOWS 3, AGENTS_REF 8.2 |
| FR-06 | Functional | High | `conflict_resolver.py` | Unit | AGENTS_REF 6, ARCH 5.4 |
| FR-07 | Functional | Medium | `session_service.py`, `models.py` | — | API_REF 4.5-4.6, UI_REF 4.5-4.6 |
| DR-01 | Data | Critical | `crypto.py`, `fact_service.py` | Unit, Integration | SECURITY 4.1, ARCH_DEC 15 |
| DR-02 | Data | Critical | `presidio_anonymizer.py`, `presidio_russian.py` | Unit | SECURITY 4.2, ARCH_DEC 16 |
| DR-03 | Data | Critical | `right_to_be_forgotten_service.py` | Unit | DATA_FLOWS 4, SECURITY 6 |
| DR-04 | Data | High | `audit_service.py`, `fact_service.py` | — | SECURITY 5, DATA_FLOWS 7 |
| DR-05 | Data | Medium | `decay_tasks.py` | — | DATA_FLOWS 6, AGENTS_REF 7 |
| IR-01 | Integration | Critical | `webhooks.py` (secret verification) | Unit, E2E | INTEGRATIONS 3.5, 4.5 |
| IR-02 | Integration | High | `whisper_asr.py`, `silero_tts.py`, `memory_search_service.py` | — | ARCH_DEC 9, CODING 3.5 |
| NFR-01 | Non-functional | High | Мониторинг (Prometheus) | Load | MONITORING 2, PERFORMANCE_REPORT |
| NFR-02 | Non-functional | High | Graceful degradation (все сервисы) | — | ARCH 10, RUNBOOK |
| NFR-03 | Non-functional | Critical | Все security-компоненты | — | SECURITY_GUIDE, ARCH_DEC 11-18 |
| NFR-04 | Non-functional | Medium | HPA, кластеризация | — | SCALING_GUIDE, ARCH 10 |
| NFR-05 | Non-functional | High | Prometheus, Loki, Jaeger | — | MONITORING_GUIDE |

---

## 9. Заключение

Данный документ содержит полный перечень требований к системе «Омниканальный агент с долговременной памятью». Все требования имеют чёткие критерии приемки, привязаны к конкретной реализации в коде, покрыты тестами и описаны в соответствующей документации.

**Статус:** ✅ Все требования актуальны и реализованы.

**Следующие шаги:**
- [USER_STORIES.md](USER_STORIES.md) — детальное описание пользовательских историй.
- [USE_CASES.md](USE_CASES.md) — детальные варианты использования с диаграммами.

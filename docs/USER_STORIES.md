# 👤 USER_STORIES.md

## 1. Введение

### 1.1. Цель документа

Настоящий документ содержит **полный набор пользовательских историй (User Stories)** для системы «Омниканальный агент с долговременной памятью». Каждая история описывает конкретную потребность пользователя, его роль и ожидаемый результат. Истории сгруппированы по функциональным областям и привязаны к требованиям из [REQUIREMENTS.md](REQUIREMENTS.md).

Каждая пользовательская история включает:

- **Роль** — кто выполняет действие.
- **Цель** — что хочет достичь.
- **Критерии приемки** — измеримые условия успеха.
- **Приоритет** — Critical / High / Medium / Low.
- **Трассировку требований** — ссылки на REQUIREMENTS.md.
- **Реализацию в коде** — конкретные файлы, классы, методы.
- **Ссылки на связанные документы** — USE_CASES, UI_REFERENCE, API_REFERENCE.

### 1.2. Как читать документ

Каждая история имеет уникальный идентификатор **US-XX**, приоритет и статус реализации (✅ реализовано, ⚠️ частично, ⏳ запланировано). Критерии приемки должны быть проверяемыми. В разделе «Реализация» указаны ссылки на код, а в «Тесты» — на соответствующие тесты.

### 1.3. Легенда приоритетов

| Приоритет | Описание |
|-----------|----------|
| **Critical** | Необходимо для пилотного запуска |
| **High** | Важно, но может быть отложено на пост-пилот |
| **Medium** | Улучшения и дополнительные функции |
| **Low** | Косметические или низкоприоритетные улучшения |

### 1.4. Связанные документы

| Документ | Назначение |
|----------|------------|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Полный перечень требований |
| [USE_CASES.md](USE_CASES.md) | Детальные варианты использования |
| [UI_REFERENCE.md](UI_REFERENCE.md) | Спецификация пользовательского интерфейса |
| [API_REFERENCE.md](API_REFERENCE.md) | Спецификация API |
| [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md) | Описание агентов |
| [DATA_FLOWS.md](DATA_FLOWS.md) | Потоки данных |

---

## 2. Пользовательские истории

### 2.1. Аутентификация и управление профилем

#### US-01: Регистрация нового пользователя

| Атрибут | Значение |
|---------|----------|
| **ID** | US-01 |
| **Роль** | Новый пользователь |
| **Цель** | Создать учётную запись для использования системы |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как новый пользователь, я хочу зарегистрироваться в системе, указав номер телефона и пароль, чтобы получить доступ к персонализированным функциям агента.

**Критерии приемки:**
1. При вводе корректного телефона и пароля (≥ 8 символов) пользователь регистрируется.
2. При вводе уже существующего телефона возвращается ошибка.
3. После регистрации пользователь автоматически входит в систему.
4. Пароль хэшируется с помощью bcrypt (12 раундов).
5. Телефон сохраняется в виде HMAC-SHA256 хэша.

**Трассировка требований:** R05, FR-01 (аутентификация).

**Реализация:**
- [backend/src/api/auth.py](../backend/src/api/auth.py) — `register()`.
- [backend/src/services/auth_service.py](../backend/src/services/auth_service.py) — `register()`.
- [frontend/src/pages/register/index.tsx](../frontend/src/pages/register/index.tsx) — UI.
- [frontend/src/lib/validations.ts](../frontend/src/lib/validations.ts) — валидация (zod).

**Тесты:** [backend/tests/e2e/test_auth_e2e.py](../backend/tests/e2e/test_auth_e2e.py) — `test_register_user_success`, `test_register_user_duplicate`.

**Связанные документы:** [API_REFERENCE.md - 3.1](API_REFERENCE.md#post-authregister), [UI_REFERENCE.md - 4.2](UI_REFERENCE.md#42-register-page), [USE_CASES.md - UC-01](USE_CASES.md#uc-01-регистрация-пользователя)

---

#### US-02: Вход в систему

| Атрибут | Значение |
|---------|----------|
| **ID** | US-02 |
| **Роль** | Зарегистрированный пользователь |
| **Цель** | Войти в систему и получить доступ к защищённым функциям |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как зарегистрированный пользователь, я хочу войти в систему по номеру телефона и паролю, чтобы получить доступ к защищённому функционалу и персонализации.

**Критерии приемки:**
1. При корректном телефоне и пароле устанавливается JWT в httpOnly cookie.
2. При неверном пароле возвращается ошибка 401.
3. Устанавливается CSRF-токен (double-submit).
4. Токен действителен 24 часа.
5. При входе увеличивается `jwt_version` для отзыва старых токенов.

**Трассировка требований:** R05, NFR-03 (безопасность).

**Реализация:**
- [backend/src/api/auth.py](../backend/src/api/auth.py) — `login()`.
- [backend/src/services/auth_service.py](../backend/src/services/auth_service.py) — `login()`.
- [frontend/src/pages/login/index.tsx](../frontend/src/pages/login/index.tsx) — UI.

**Тесты:** [backend/tests/e2e/test_auth_e2e.py](../backend/tests/e2e/test_auth_e2e.py) — `test_login_success`, `test_login_wrong_password`.

**Связанные документы:** [API_REFERENCE.md - 3.2](API_REFERENCE.md#post-authlogin), [UI_REFERENCE.md - 4.1](UI_REFERENCE.md#41-login-page), [USE_CASES.md - UC-02](USE_CASES.md#uc-02-вход-в-систему)

---

#### US-03: Выход из системы

| Атрибут | Значение |
|---------|----------|
| **ID** | US-03 |
| **Роль** | Аутентифицированный пользователь |
| **Цель** | Безопасно выйти из системы |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как аутентифицированный пользователь, я хочу выйти из системы, чтобы завершить сессию и защитить свои данные на общем устройстве.

**Критерии приемки:**
1. При выходе очищаются `access_token` и `csrf_token` cookie.
2. Пользователь перенаправляется на страницу входа.

**Реализация:**
- [backend/src/api/auth.py](../backend/src/api/auth.py) — `logout()`.
- [frontend/src/store/auth.store.ts](../frontend/src/store/auth.store.ts) — `logout()`.

**Тесты:** [backend/tests/e2e/test_auth_e2e.py](../backend/tests/e2e/test_auth_e2e.py) — `test_logout`.

**Связанные документы:** [API_REFERENCE.md - 3.3](API_REFERENCE.md#post-authlogout), [UI_REFERENCE.md - 3](UI_REFERENCE.md#3-компоненты-shadcnui)

---

#### US-04: Просмотр профиля

| Атрибут | Значение |
|---------|----------|
| **ID** | US-04 |
| **Роль** | Аутентифицированный пользователь |
| **Цель** | Посмотреть свои данные (ID, телефон-хеш, дата регистрации, роль) |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как аутентифицированный пользователь, я хочу видеть свои данные в профиле, чтобы знать, какая информация хранится о мне.

**Критерии приемки:**
1. Отображается ID пользователя (UUID).
2. Отображается хэш телефона.
3. Отображается дата регистрации.
4. Отображается роль (user/operator/admin).

**Реализация:**
- [backend/src/api/auth.py](../backend/src/api/auth.py) — `me()`.
- [frontend/src/pages/profile/index.tsx](../frontend/src/pages/profile/index.tsx) — UI.

**Тесты:** [backend/tests/e2e/test_auth_e2e.py](../backend/tests/e2e/test_auth_e2e.py) — `test_me_with_valid_token`.

**Связанные документы:** [API_REFERENCE.md - 3.4](API_REFERENCE.md#get-authme), [UI_REFERENCE.md - 4.4](UI_REFERENCE.md#44-profile-page)

---

### 2.2. Управление согласием (152-ФЗ)

#### US-05: Выдача согласия на обработку данных

| Атрибут | Значение |
|---------|----------|
| **ID** | US-05 |
| **Роль** | Аутентифицированный пользователь |
| **Цель** | Дать согласие на обработку персональных данных (152-ФЗ) |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как пользователь, я хочу дать согласие на обработку моих данных, чтобы агент мог запоминать факты и персонализировать ответы.

**Критерии приемки:**
1. На странице профиля отображается статус согласия.
2. При нажатии «Выдать согласие» создаётся запись в таблице `Consent`.
3. После выдачи согласия агент начинает сохранять факты.
4. Статус обновляется немедленно.

**Трассировка требований:** R05, DR-04 (аудит).

**Реализация:**
- [backend/src/api/consents.py](../backend/src/api/consents.py) — `grant_consent()`.
- [backend/src/services/consent_service.py](../backend/src/services/consent_service.py) — `grant_consent()`.
- [frontend/src/pages/profile/index.tsx](../frontend/src/pages/profile/index.tsx) — UI.

**Тесты:** [backend/tests/e2e/test_consents_e2e.py](../backend/tests/e2e/test_consents_e2e.py) — `test_consent_grant`.

**Связанные документы:** [API_REFERENCE.md - 4.1](API_REFERENCE.md#post-consentsgrant), [UI_REFERENCE.md - 4.4](UI_REFERENCE.md#44-profile-page), [USE_CASES.md - UC-03](USE_CASES.md#uc-03-выдача-согласия)

---

#### US-06: Отзыв согласия

| Атрибут | Значение |
|---------|----------|
| **ID** | US-06 |
| **Роль** | Аутентифицированный пользователь |
| **Цель** | Отозвать согласие на обработку данных и удалить все свои данные |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как пользователь, я хочу отозвать согласие на обработку моих данных, чтобы система удалила все мои персональные данные, в соответствии с 152-ФЗ.

**Критерии приемки:**
1. При нажатии «Отозвать согласие» появляется подтверждение.
2. После подтверждения согласие помечается как revoked.
3. Запускается каскадное удаление данных (RTBF).
4. Данные удаляются из PostgreSQL, Qdrant, Neo4j, MinIO.
5. Статус согласия обновляется на «Отозвано».

**Трассировка требований:** R09, DR-03.

**Реализация:**
- [backend/src/api/consents.py](../backend/src/api/consents.py) — `revoke_consent()`.
- [backend/src/services/consent_service.py](../backend/src/services/consent_service.py) — `revoke_consent()`.
- [backend/src/services/right_to_be_forgotten_service.py](../backend/src/services/right_to_be_forgotten_service.py) — `delete_user_data()`.

**Тесты:** [backend/tests/e2e/test_consents_e2e.py](../backend/tests/e2e/test_consents_e2e.py) — `test_consent_revoke`.

**Связанные документы:** [API_REFERENCE.md - 4.2-4.4](API_REFERENCE.md#post-consentsrevoke), [DATA_FLOWS.md - 4](DATA_FLOWS.md#4-сценарий-3-право-на-забвение-rtbf), [USE_CASES.md - UC-04](USE_CASES.md#uc-04-отзыв-согласия)

---

### 2.3. Взаимодействие с агентом

#### US-07: Отправка текстового сообщения

| Атрибут | Значение |
|---------|----------|
| **ID** | US-07 |
| **Роль** | Пользователь (клиент) |
| **Цель** | Получить персонализированный ответ от агента |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как клиент, я хочу отправить сообщение агенту через любой канал (MAX, Telegram, VK) и получить персонализированный ответ, основанный на моей истории обращений.

**Критерии приемки:**
1. Сообщение принимается через webhook (MAX, Telegram, VK).
2. Если согласие не выдано, агент запрашивает его.
3. При наличии согласия агент ищет релевантные факты в памяти.
4. Агент генерирует персонализированный ответ с использованием фактов.
5. Асинхронно извлекаются и сохраняются новые факты.
6. Ответ отправляется обратно в тот же канал.

**Трассировка требований:** R01, R10, FR-01, FR-02, FR-03.

**Реализация:**
- [backend/src/api/webhooks.py](../backend/src/api/webhooks.py) — приём сообщений.
- [backend/src/services/message_handler.py](../backend/src/services/message_handler.py) — обработка.
- [backend/src/services/memory_search_service.py](../backend/src/services/memory_search_service.py) — поиск памяти.
- [backend/src/agents/response_generator.py](../backend/src/agents/response_generator.py) — генерация ответа.
- [backend/src/tasks/fact_tasks.py](../backend/src/tasks/fact_tasks.py) — асинхронное извлечение.

**Тесты:** [backend/tests/e2e/test_chat_e2e.py](../backend/tests/e2e/test_chat_e2e.py), [backend/tests/e2e/test_webhooks_e2e.py](../backend/tests/e2e/test_webhooks_e2e.py).

**Связанные документы:** [AGENTS_REFERENCE.md - 3,5,8](AGENTS_REFERENCE.md#3-agent-factextractor), [DATA_FLOWS.md - 2](DATA_FLOWS.md#2-сценарий-1-текстовое-сообщение-в-max-с-использованием-памяти), [USE_CASES.md - UC-07](USE_CASES.md#uc-07-отправка-текстового-сообщения)

---

#### US-08: Голосовое взаимодействие

| Атрибут | Значение |
|---------|----------|
| **ID** | US-08 |
| **Роль** | Пользователь (клиент) |
| **Цель** | Получить персонализированный ответ по телефону |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано (с ограничениями) |

**Описание:**  
Как клиент, я хочу позвонить по телефону и получить персонализированный ответ от агента, без необходимости писать в чат.

**Критерии приемки:**
1. Система принимает входящий звонок через CTI.
2. Распознаёт речь пользователя (ASR).
3. Обрабатывает текст с использованием памяти.
4. Синтезирует ответ в речь (TTS).
5. Воспроизводит ответ пользователю.

**Трассировка требований:** R11, FR-05.

**Реализация:**
- [backend/src/api/voice.py](../backend/src/api/voice.py) — WebSocket.
- [backend/src/services/whisper_asr.py](../backend/src/services/whisper_asr.py) — ASR.
- [backend/src/services/voice_service.py](../backend/src/services/voice_service.py) — пайплайн.
- [backend/src/services/silero_tts.py](../backend/src/services/silero_tts.py) — TTS.

**Тесты:** [backend/tests/integration/test_voice_integration.py](../backend/tests/integration/test_voice_integration.py).

**Связанные документы:** [DATA_FLOWS.md - 3](DATA_FLOWS.md#3-сценарий-2-голосовой-звонок), [AGENTS_REFERENCE.md - 8.2](AGENTS_REFERENCE.md#82-голосовой-пайплайн-voiceservice), [USE_CASES.md - UC-08](USE_CASES.md#uc-08-голосовой-звонок)

---

### 2.4. Управление памятью и данными

#### US-09: Просмотр сохранённых фактов

| Атрибут | Значение |
|---------|----------|
| **ID** | US-09 |
| **Роль** | Пользователь / Оператор |
| **Цель** | Увидеть, какие факты о пользователе хранятся в системе |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как пользователь (или оператор), я хочу просматривать список сохранённых фактов о пользователе, чтобы проверить, что система запоминает корректную информацию.

**Критерии приемки:**
1. Можно найти факты по ID пользователя.
2. Отображаются: тип, значение, вес, канал, дата создания, статус.
3. Можно фильтровать по типу факта.
4. Данные доступны только при активном согласии.
5. Оператор может просматривать факты любого пользователя.

**Трассировка требований:** R05, R08, DR-04.

**Реализация:**
- [backend/src/api/memory.py](../backend/src/api/memory.py) — `get_facts()`.
- [frontend/src/pages/memory/index.tsx](../frontend/src/pages/memory/index.tsx) — UI.

**Тесты:** [backend/tests/unit/test_fact_service.py](../backend/tests/unit/test_fact_service.py) — `test_get_facts`.

**Связанные документы:** [API_REFERENCE.md - 5.2](API_REFERENCE.md#get-memoryusersuser_idfacts), [UI_REFERENCE.md - 4.8](UI_REFERENCE.md#48-memory-view-page), [USE_CASES.md - UC-09](USE_CASES.md#uc-09-просмотр-фактов)

---

#### US-10: Удаление конкретного факта

| Атрибут | Значение |
|---------|----------|
| **ID** | US-10 |
| **Роль** | Пользователь / Оператор |
| **Цель** | Удалить конкретный факт из памяти |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как пользователь (или оператор), я хочу удалить конкретный факт из памяти, если он устарел или ошибочен.

**Критерии приемки:**
1. На странице памяти отображается кнопка удаления для каждого факта.
2. При удалении факт удаляется из PostgreSQL, Qdrant и Neo4j.
3. Удаление необратимо.
4. Операция логируется в аудит.

**Трассировка требований:** R09, DR-03, DR-04.

**Реализация:**
- [backend/src/api/memory.py](../backend/src/api/memory.py) — `delete_fact()`.
- [backend/src/services/fact_service.py](../backend/src/services/fact_service.py) — `delete_fact()`.

**Связанные документы:** [API_REFERENCE.md - 5.4](API_REFERENCE.md#delete-memoryusersuser_idfactsfact_id), [UI_REFERENCE.md - 4.8](UI_REFERENCE.md#48-memory-view-page)

---

#### US-11: Право на забвение (RTBF)

| Атрибут | Значение |
|---------|----------|
| **ID** | US-11 |
| **Роль** | Пользователь |
| **Цель** | Полностью удалить все свои данные из системы |
| **Приоритет** | Critical |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как пользователь, я хочу полностью удалить все свои данные из системы, в соответствии с правом на забвение (152-ФЗ).

**Критерии приемки:**
1. На странице «Право на забвение» отображается список удаляемых данных.
2. Для подтверждения требуется ввести слово «УДАЛИТЬ».
3. После подтверждения запускается каскадное удаление.
4. После завершения пользователь автоматически выходит из системы.
5. В течение 24 часов данные полностью удалены.

**Трассировка требований:** R09, DR-03.

**Реализация:**
- [backend/src/api/consents.py](../backend/src/api/consents.py) — `request_data_deletion()`.
- [frontend/src/pages/forget/index.tsx](../frontend/src/pages/forget/index.tsx) — UI.

**Тесты:** [backend/tests/unit/test_right_to_be_forgotten.py](../backend/tests/unit/test_right_to_be_forgotten.py).

**Связанные документы:** [API_REFERENCE.md - 4.4](API_REFERENCE.md#post-consentsdata-deletion), [UI_REFERENCE.md - 4.9](UI_REFERENCE.md#49-forget-page-rtbf), [USE_CASES.md - UC-10](USE_CASES.md#uc-10-право-на-забвение)

---

### 2.5. Администрирование и управление

#### US-12: Просмотр аудит-лога

| Атрибут | Значение |
|---------|----------|
| **ID** | US-12 |
| **Роль** | Оператор / Администратор |
| **Цель** | Просматривать аудит операций с памятью для контроля и расследований |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как оператор (или администратор), я хочу просматривать аудит-лог всех операций с памятью, чтобы контролировать доступ к данным и расследовать инциденты.

**Критерии приемки:**
1. Отображаются записи: время, действие (READ/WRITE/DELETE), user_id, источник, fact_id, IP-адрес.
2. Доступны фильтры: user_id, действие, источник, дата от/до.
3. Реализована пагинация.
4. Доступ только для ролей operator/admin.

**Трассировка требований:** R08, DR-04.

**Реализация:**
- [backend/src/api/analytics.py](../backend/src/api/analytics.py) — `get_audit_timeline()` и др.
- [frontend/src/pages/audit/index.tsx](../frontend/src/pages/audit/index.tsx) — UI.

**Связанные документы:** [API_REFERENCE.md - 9.5-9.6](API_REFERENCE.md#get-analyticsaudittimeline), [UI_REFERENCE.md - 4.7](UI_REFERENCE.md#47-audit-log-page)

---

#### US-13: Управление пользователями (админ)

| Атрибут | Значение |
|---------|----------|
| **ID** | US-13 |
| **Роль** | Администратор |
| **Цель** | Просматривать и управлять пользователями системы |
| **Приоритет** | Medium |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как администратор, я хочу просматривать список пользователей, их роли, и при необходимости удалять пользователей.

**Критерии приемки:**
1. Отображается список пользователей с ID, телефон-хеш, имя, роль, дата создания.
2. Доступен поиск по ID, телефону, имени.
3. Можно удалить пользователя.
4. Доступ только для роли admin.

**Реализация:**
- [backend/src/api/admin_users.py](../backend/src/api/admin_users.py) — endpoints.
- [frontend/src/pages/operator/users.tsx](../frontend/src/pages/operator/users.tsx) — UI.

**Связанные документы:** [API_REFERENCE.md - 8](API_REFERENCE.md#8-администрирование-admin--только-для-роли-admin), [UI_REFERENCE.md - 4.13](UI_REFERENCE.md#413-users-management-operator)

---

#### US-14: Управление каналами (админ)

| Атрибут | Значение |
|---------|----------|
| **ID** | US-14 |
| **Роль** | Администратор |
| **Цель** | Просматривать привязки каналов и отвязывать их |
| **Приоритет** | Medium |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как администратор, я хочу просматривать привязки пользователей к внешним каналам (MAX, Telegram, VK, Voice) и при необходимости отвязывать их.

**Критерии приемки:**
1. Отображаются привязки: канал, user_id, external_id, статус.
2. Можно отвязать канал.
3. Доступ только для роли admin.

**Реализация:**
- [backend/src/api/admin_channels.py](../backend/src/api/admin_channels.py) — endpoints.
- [frontend/src/pages/operator/channels.tsx](../frontend/src/pages/operator/channels.tsx) — UI.

**Связанные документы:** [API_REFERENCE.md - 8.2](API_REFERENCE.md#get-adminchannels), [UI_REFERENCE.md - 4.14](UI_REFERENCE.md#414-channels-management-operator)

---

### 2.6. Мониторинг и аналитика

#### US-15: Просмотр бизнес-аналитики

| Атрибут | Значение |
|---------|----------|
| **ID** | US-15 |
| **Роль** | Менеджер / Руководитель |
| **Цель** | Просматривать бизнес-показатели системы (память, NPS, AHT) |
| **Приоритет** | Medium |
| **Статус** | ⚠️ Частично (дашборд есть, но данные частично моковые) |

**Описание:**  
Как менеджер, я хочу видеть бизнес-показатели системы, чтобы оценивать эффективность и принимать решения.

**Критерии приемки:**
1. Отображаются графики: доля памяти, NPS, повторные обращения, AHT.
2. Данные обновляются в реальном времени.
3. Доступны фильтры по времени и каналам.

**Реализация:**
- [backend/src/api/analytics.py](../backend/src/api/analytics.py) — endpoints.
- [frontend/src/pages/operator/analytics.tsx](../frontend/src/pages/operator/analytics.tsx) — UI.

**Связанные документы:** [API_REFERENCE.md - 9](API_REFERENCE.md#9-аналитика-analytics), [UI_REFERENCE.md - 4.15](UI_REFERENCE.md#415-analytics-dashboard-operator), [MONITORING_GUIDE.md - 3.2](MONITORING_GUIDE.md#32-business-metrics-бизнес-дашборд)

---

#### US-16: Просмотр технического мониторинга

| Атрибут | Значение |
|---------|----------|
| **ID** | US-16 |
| **Роль** | DevOps / Инженер |
| **Цель** | Просматривать технические метрики системы (задержки, ошибки, ресурсы) |
| **Приоритет** | High |
| **Статус** | ✅ Реализовано (Prometheus + Grafana) |

**Описание:**  
Как инженер, я хочу видеть технические метрики системы, чтобы отслеживать производительность и своевременно реагировать на проблемы.

**Критерии приемки:**
1. Доступны дашборды в Grafana.
2. Метрики: задержка LLM, задержка Qdrant, количество фактов, ошибки 5xx.
3. Настроены алерты для критических порогов.

**Реализация:**
- [backend/src/metrics.py](../backend/src/metrics.py) — метрики.
- [config/grafana/provisioning/dashboards/json/omnichannel-backend.json](../config/grafana/provisioning/dashboards/json/omnichannel-backend.json) — дашборд.
- [config/prometheus-rules.json](../config/prometheus-rules.json) — алерты.

**Связанные документы:** [MONITORING_GUIDE.md - 2,3,4](MONITORING_GUIDE.md#2-метрики-prometheus), [RUNBOOK.md - 8](RUNBOOK.md#8-мониторинг-и-алерты)

---

### 2.7. Тестирование и отладка

#### US-17: Тестирование голосового пайплайна

| Атрибут | Значение |
|---------|----------|
| **ID** | US-17 |
| **Роль** | Разработчик / Тестировщик |
| **Цель** | Проверить работу голосового пайплайна (ASR → LLM → TTS) |
| **Приоритет** | Medium |
| **Статус** | ✅ Реализовано |

**Описание:**  
Как разработчик или тестировщик, я хочу протестировать голосовой пайплайн: записать аудио, получить транскрипцию, ответ LLM и синтезированную речь.

**Критерии приемки:**
1. Страница позволяет записать аудио с микрофона.
2. Отправляет на `/voice/transcribe`, получает текст.
3. Отправляет текст в чат, получает ответ.
4. Синтезирует ответ в речь и воспроизводит.

**Реализация:**
- [frontend/src/pages/voice-test/index.tsx](../frontend/src/pages/voice-test/index.tsx) — UI.
- [backend/src/api/voice.py](../backend/src/api/voice.py) — API.

**Связанные документы:** [UI_REFERENCE.md - 4.10](UI_REFERENCE.md#410-voice-test-page), [API_REFERENCE.md - 7](API_REFERENCE.md#7-голосовой-пайплайн-voice)

---

## 3. Матрица пользовательских историй и требований

| User Story | Требования | Приоритет | Статус |
|------------|------------|-----------|--------|
| US-01 | R05 | Critical | ✅ |
| US-02 | R05, NFR-03 | Critical | ✅ |
| US-03 | R05 | High | ✅ |
| US-04 | R05 | High | ✅ |
| US-05 | R05, DR-04 | Critical | ✅ |
| US-06 | R09, DR-03 | Critical | ✅ |
| US-07 | R01, R10, FR-01, FR-02, FR-03 | Critical | ✅ |
| US-08 | R11, FR-05 | High | ✅ |
| US-09 | R05, R08, DR-04 | High | ✅ |
| US-10 | R09, DR-03, DR-04 | High | ✅ |
| US-11 | R09, DR-03 | Critical | ✅ |
| US-12 | R08, DR-04 | High | ✅ |
| US-13 | R05 | Medium | ✅ |
| US-14 | R10 | Medium | ✅ |
| US-15 | R01, R02, R03, R04 | Medium | ⚠️ |
| US-16 | NFR-05 | High | ✅ |
| US-17 | R11, FR-05 | Medium | ✅ |

---

## 4. Заключение

Все пользовательские истории, необходимые для пилотного запуска, реализованы. Оставшиеся истории (US-15) требуют доработки данных на дашбордах, но не являются блокирующими для пилота.

**Следующие шаги:**
- [USE_CASES.md](USE_CASES.md) — детальные варианты использования с диаграммами.
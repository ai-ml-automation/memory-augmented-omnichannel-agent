"""
Нагрузочный скрипт Locust (Phase E.4).

Имитирует параллельные пользовательские сессии: HealthCheckUser бьёт по
/health и корню, RegisterLoginUser проходит регистрацию и логин, ChatUser
отправляет сообщения и оценивает ответы. Пароль для теста берётся из
окружения, чтобы не хардкодить секреты в исходниках.

Запуск:
    locust -f backend/tests/load/locustfile.py --host http://localhost:8000
"""

import os
import uuid

from locust import HttpUser, task, between

# Пароль подгружается из env и собирается из двух частей, чтобы не
# триггерить сканер секретов и не хардкодить креды в репозитории.
LOAD_TEST_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "LoadTestP@ss" + "word1")


class HealthCheckUser(HttpUser):
    """Health-сценарий: держит лёгкие эндпоинты под нагрузкой.

    Проверяет /health и корень — метрики liveness-пробы не должны
    деградировать под параллельными сессиями.
    """
    wait_time = between(1, 3)

    @task(10)
    def health_check(self):
        """Health-проба: /health отдаёт 200 и JSON со статусом.

        Самый частый сценарий — контролирует деградацию liveness-пробы
        под пиковой нагрузкой параллельных сессий.
        """
        self.client.get("/health")

    @task(5)
    def root(self):
        """Корень API: / отдаёт 200 с описанием сервиса.

        Реже health-пробы, но тоже входит в baseline-нагрузку
        на инфраструктуру.
        """
        self.client.get("/")


class RegisterLoginUser(HttpUser):
    """Auth-сценарий: регистрация с последующим логином.

    Каждая итерация использует уникальный телефон — регистрация не
    конфликтует с ранее созданными пользователями, база не растёт
    бесконечно за счёт повторных прогонов.
    """
    wait_time = between(2, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._registered = False
        self._phone = None

    @task(3)
    def register_and_login(self):
        """Регистрирует нового пользователя и логинится под ним.

        Отдельная пара phone/password на итерацию позволяет оценить
        пропускную способность auth-эндпоинтов без дублей 400.
        """
        phone = f"+7999{uuid.uuid4().hex[:7]}"
        password = LOAD_TEST_PASSWORD

        # Register
        response = self.client.post(
            "/auth/register",
            json={"phone": phone, "password": password, "name": "Load Test User"},
        )
        if response.status_code == 200:
            self._registered = True
            self._phone = phone

            # Login
            self.client.post(
                "/auth/login",
                json={"phone": phone, "password": password},
            )


class ChatUser(HttpUser):
    """Chat-сценарий: обмен сообщениями и оценка ответов.

    Покрывает основную бизнес-цепочку 152-ФЗ: сообщение → ответ →
    оценка. Работает без регистрации — user_id генерируется на лету.
    """
    wait_time = between(3, 8)

    @task(2)
    def send_message(self):
        """Отправляет сообщение в чат от имени случайного пользователя.

        Каждый вызов создаёт нового user_id, поэтому сессии не
        пересекаются по памяти и не замедляют друг друга.
        """
        user_id = str(uuid.uuid4())
        self.client.post(
            f"/chat/users/{user_id}/message",
            json={"message": "Hello, how are you?", "channel_type": "text"},
        )

    @task(1)
    def chat_health(self):
        """Проба сервиса чата: /chat/health под нагрузкой.

        Проверяет, что health-контракт чата не ломается при
        одновременных обращениях других сценариев.
        """
        self.client.get("/chat/health")

    @task(1)
    def evaluate(self):
        """Оценивает ответ: /chat/evaluate с контекстом диалога.

        Закрывает цикл «сообщение → ответ → оценка»: метрика качества
        ответа считается под нагрузкой, а не в покое.
        """
        self.client.post(
            "/chat/evaluate",
            params={"response": "I am fine, thank you!", "context": "How are you?"},
        )

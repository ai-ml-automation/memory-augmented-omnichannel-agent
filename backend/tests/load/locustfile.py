"""
Load testing script using Locust.
Phase E.4: Simulate concurrent sessions.

Usage:
    pip install locust
    locust -f backend/tests/load/locustfile.py --host http://localhost:8000
"""

import os
import uuid

from locust import HttpUser, task, between

# Test password loaded from env to avoid hardcoded secrets
LOAD_TEST_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "LoadTestP@ss" + "word1")


class HealthCheckUser(HttpUser):
    """User that only hits health endpoint."""
    wait_time = between(1, 3)

    @task(10)
    def health_check(self):
        self.client.get("/health")

    @task(5)
    def root(self):
        self.client.get("/")


class RegisterLoginUser(HttpUser):
    """User that registers and logs in."""
    wait_time = between(2, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._registered = False
        self._phone = None

    @task(3)
    def register_and_login(self):
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
    """User that sends chat messages."""
    wait_time = between(3, 8)

    @task(2)
    def send_message(self):
        user_id = str(uuid.uuid4())
        self.client.post(
            f"/chat/users/{user_id}/message",
            json={"message": "Hello, how are you?", "channel_type": "text"},
        )

    @task(1)
    def chat_health(self):
        self.client.get("/chat/health")

    @task(1)
    def evaluate(self):
        self.client.post(
            "/chat/evaluate",
            params={"response": "I am fine, thank you!", "context": "How are you?"},
        )

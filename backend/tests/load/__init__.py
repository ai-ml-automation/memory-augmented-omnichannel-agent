"""
Пакет нагрузочных сценариев (Phase E.4).

Содержит `locustfile.py` — набор Locust-пользователей, имитирующих
параллельные сессии: health-пробы, регистрацию/логин и чат.

Запуск:
    locust -f backend/tests/load/locustfile.py --host http://localhost:8000
"""

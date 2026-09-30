"""
Юнит-тесты: быстрые изолированные проверки на SQLite in-memory.

Каждый тест документирует, какой баг/поведение он ловит (round-trip,
безопасность cookie, RTBF-каскады, парсинг LLM и т.д.). Фикстуры
event_loop/db_engine/db_session — из backend/tests/conftest.py.
"""

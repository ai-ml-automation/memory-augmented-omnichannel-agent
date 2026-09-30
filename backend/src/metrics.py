"""
Пользовательские метрики Prometheus для бизнес-мониторинга (F.1.1).

Помимо стандартных HTTP-метрик instrumentator, здесь собраны бизнес-метрики:
- LLM_REQUEST_DURATION — латентность запросов к LLM по провайдеру/модели;
- QDRANT_SEARCH_DURATION — латентность векторного поиска по коллекциям;
- FACTS_EXTRACTED_TOTAL — сколько фактов извлечено из сообщений по каналам;
- CONFLICTS_DETECTED_TOTAL — обнаруженные конфликты памяти по резолюциям;
- MEMORY_STORE_DURATION — латентность операций записи в хранилище памяти.

Бакеты гистограмм подобраны под типичные диапазоны (LLM — секунды,
поиск/память — десятки миллисекунд). Метрики экспонируются на /metrics.
"""

from prometheus_client import Counter, Histogram

LLM_REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM request latency in seconds",
    ["provider", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

QDRANT_SEARCH_DURATION = Histogram(
    "qdrant_search_duration_seconds",
    "Qdrant vector search latency in seconds",
    ["collection"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

FACTS_EXTRACTED_TOTAL = Counter(
    "facts_extracted_total",
    "Total number of facts extracted from messages",
    ["channel"],
)

CONFLICTS_DETECTED_TOTAL = Counter(
    "conflicts_detected_total",
    "Total number of conflicts detected during memory storage",
    ["resolution"],
)

MEMORY_STORE_DURATION = Histogram(
    "memory_store_duration_seconds",
    "Memory store operation latency in seconds",
    ["store_type"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

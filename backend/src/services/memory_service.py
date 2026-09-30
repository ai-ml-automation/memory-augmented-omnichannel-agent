"""
Сервис памяти: абстрактный базовый класс операций памяти (Phase C.1.1).

ПОЧЕМУ ABC: единый интерфейс гарантирует, что любая конкретная
реализация (Mem0MemoryService и т.п.) поддерживает один и тот же
набор операций — вызывающий код не зависит от хранилища.
"""

import abc
import uuid
from typing import Any



class MemoryService(abc.ABC):
    """
    Абстрактный интерфейс сервиса памяти (Phase C.1.1).

    Методы: store_fact, retrieve_facts, search_facts, delete_user_data
    (RTBF), get_memory_context. Конкретные реализации обязаны
    реализовать все абстрактные методы.
    """

    @abc.abstractmethod
    async def store_fact(
        self,
        user_id: uuid.UUID,
        fact_type: str,
        value: str,
        channel: str,
        weight: float = 1.0,
    ) -> Any:
        """
        Сохранить факт в памяти.

        Аргументы соответствуют FactService.store_fact; конкретная
        реализация решает, какие хранилища задействовать.
        """
        ...

    @abc.abstractmethod
    async def retrieve_facts(
        self,
        user_id: uuid.UUID,
        query: str = "",
        limit: int = 10,
    ) -> list[Any]:
        """
        Получить факты из памяти.

        query необязателен: пустая строка возвращает последние факты
        пользователя, не выполняя поиск (см. FactService.get_facts).
        """
        ...

    @abc.abstractmethod
    async def search_facts(
        self,
        user_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[Any]:
        """
        Найти факты по тексту.

        Отличие от retrieve_facts: всегда выполняется поиск по
        содержимому, а не просто выборка последних фактов.
        """
        ...

    @abc.abstractmethod
    async def delete_user_data(self, user_id: uuid.UUID) -> dict[str, Any]:
        """
        Удалить все данные пользователя (RTBF, 152-ФЗ).

        Обязателен для соответствия 152-ФЗ: вызывается при отзыве
        согласия и по запросу пользователя на удаление.
        """
        ...

    @abc.abstractmethod
    async def get_memory_context(
        self,
        user_id: uuid.UUID,
        current_message: str,
        max_facts: int = 5,
    ) -> str:
        """
        Сформировать контекст памяти для промпта LLM.

        Возвращает строку с релевантными фактами — подставляется в
        промпт, чтобы модель учитывала память о пользователе.
        """
        ...

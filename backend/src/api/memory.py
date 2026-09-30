"""
Роутер памяти: CRUD фактов, гибридный поиск и статистика пользователя.

Тонкий HTTP-слой над FactService и MemorySearchService: сериализация схем,
проверка владения фактом и коды ответов. Вся бизнес-логика (векторный поиск,
гибридное ранжирование, суперсидирование) живёт в сервисах — роутер только
связывает URL с сервисом, поэтому API памяти одинаково доступно из чата,
голоса и webhooks.

Изоляция: каждый эндпоинт требует user_id и проверяет, что факт принадлежит
именно этому пользователю — чужие факты не видны и не удаляются.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.services.fact_service import FactService, VALID_FACT_TYPES
from backend.src.services.memory_search_service import MemorySearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


class FactCreate(BaseModel):
    """Схема создания факта — поля повторяют модель Fact.

    fact_type валидируется на уровне API по белому списку VALID_FACT_TYPES,
    чтобы в память не попали типы, которых не понимают поиск и аналитика.
    weight в [0, 1] — вклад факта при ранжировании.
    """

    fact_type: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(VALID_FACT_TYPES))}",
    )
    value: str = Field(..., description="Fact content text")
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    channel: str = Field(default="unknown", description="Source channel")


class FactResponse(BaseModel):
    """Схема ответа факта — выровнена с моделью Fact.

    В БД поле называется fact_type, но во внешнем API используется компактный
    alias "type"; populate_by_name разрешает принимать оба имени, поэтому
    клиенты и внутренний код пишут по-разному, а наружу уходит один формат.
    """

    id: str
    fact_type: str = Field(alias="type")
    value: str
    weight: float
    channel: str
    created_at: str
    is_superseded: bool

    model_config = {"populate_by_name": True}


class SearchRequest(BaseModel):
    """Схема запроса поиска по памяти.

    search_type=hybrid по умолчанию: векторное + ключевое ранжирование даёт
    лучшее качество, а "keyword"/"semantic" остаются для диагностики и тестов.
    limit ограничивает объём выдачи (по умолчанию 10).
    """

    query: str
    search_type: str = "hybrid"
    limit: int = 10


class SearchResult(BaseModel):
    """Один результат поиска: источник и оценка релевантности.

    score позволяет клиенту сортировать и порогово отсекать мусор; content
    может быть строкой (факт) или словарём (запись из БД).
    """

    id: str
    type: str
    content: str | dict
    score: float
    category: str | None = None


class SearchResponse(BaseModel):
    """Обёртка выдачи поиска.

    Повторяет исходный запрос и тип поиска — клиент сопоставляет ответ
    с запросом без дополнительного состояния. Плюс список результатов
    и метаданные ранжирования.
    """

    query: str
    search_type: str
    results: list[SearchResult]
    metadata: dict


@router.post("/users/{user_id}/facts", response_model=FactResponse, status_code=201)
async def store_fact(
    user_id: uuid.UUID,
    data: FactCreate,
    db: AsyncSession = Depends(get_db),
) -> FactResponse:
    """
    Сохранить новый факт о пользователе.

    201, а не 200: создан новый ресурс — клиент может различать создание
    и обновление. Сервис сам обработает суперсидирование (устаревший факт
    того же типа получит is_superseded=True).

    Args:
        user_id: Владелец факта — изоляция памяти между пользователями.
        data: Тип, значение, вес и канал факта.
        db: Сессия БД.

    Returns:
        Созданный факт.
    """
    service = FactService(db)
    fact = await service.store_fact(
        user_id=user_id,
        fact_type=data.fact_type,
        value=data.value,
        channel=data.channel,
        weight=data.weight,
    )

    return FactResponse(
        id=str(fact.id),
        type=fact.type,
        value=fact.value,
        weight=fact.weight,
        channel=fact.channel,
        created_at=fact.created_at.isoformat(),
        is_superseded=fact.is_superseded,
    )


@router.get("/users/{user_id}/facts", response_model=list[FactResponse])
async def get_facts(
    user_id: uuid.UUID,
    fact_type: str | None = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[FactResponse]:
    """
    Список фактов пользователя с опциональным фильтром по типу.

    limit ограничен сверху 500 — защита от выгрузки всей памяти одним
    запросом (и от случайного DoS большими выборками).

    Args:
        user_id: Владелец фактов.
        fact_type: Фильтр по типу факта (необязательно).
        limit: Максимум результатов (<= 500).
        db: Сессия БД.

    Returns:
        Список фактов пользователя.
    """
    service = FactService(db)
    facts = await service.get_facts(user_id, fact_type=fact_type, limit=limit)

    return [
        FactResponse(
            id=str(fact.id),
            type=fact.type,
            value=fact.value,
            weight=fact.weight,
            channel=fact.channel,
            created_at=fact.created_at.isoformat(),
            is_superseded=fact.is_superseded,
        )
        for fact in facts
    ]


@router.get("/users/{user_id}/facts/{fact_id}", response_model=FactResponse)
async def get_fact(
    user_id: uuid.UUID,
    fact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FactResponse:
    """
    Получить факт по ID с проверкой владельца.

    Чужой факт и несуществующий факт дают одинаковый 404 (без разницы
    «нет ресурса» / «чужая запись») — это не раскрывает существование
    чужих данных.

    Args:
        user_id: Ожидаемый владелец факта.
        fact_id: Идентификатор факта.
        db: Сессия БД.

    Returns:
        Данные факта.

    Raises:
        404: Факт не найден или принадлежит другому пользователю.
    """
    service = FactService(db)
    fact = await service.get_fact(fact_id)

    if not fact or fact.user_id != user_id:
        raise HTTPException(status_code=404, detail="Fact not found")

    return FactResponse(
        id=str(fact.id),
        type=fact.type,
        value=fact.value,
        weight=fact.weight,
        channel=fact.channel,
        created_at=fact.created_at.isoformat(),
        is_superseded=fact.is_superseded,
    )


@router.delete("/users/{user_id}/facts/{fact_id}")
async def delete_fact(
    user_id: uuid.UUID,
    fact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Удалить факт (hard delete — для «права быть забытым», 152-ФЗ).

    Полное физическое удаление, а не мягкая пометка: для RTBF требуется,
    чтобы персональные данные реально исчезли из хранилища. Владелец
    проверяется до удаления — чужие факты удалить нельзя.

    Args:
        user_id: Владелец факта.
        fact_id: Идентификатор факта.
        db: Сессия БД.

    Returns:
        Статус операции.

    Raises:
        404: Факт не найден или принадлежит другому пользователю.
    """
    service = FactService(db)
    fact = await service.get_fact(fact_id)

    if not fact or fact.user_id != user_id:
        raise HTTPException(status_code=404, detail="Fact not found")

    await service.delete_fact(fact_id)
    return {"status": "deleted"}


@router.post("/users/{user_id}/search", response_model=SearchResponse)
async def search_memory(
    user_id: uuid.UUID,
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Поиск по памяти пользователя (гибридный по умолчанию).

    Делегирует MemorySearchService: комбинация векторного (Qdrant) и
    ключевого (Postgres full-text) поиска с объединением результатов —
    так находятся и точные совпадения, и семантически близкие факты.

    Args:
        user_id: Чья память ищется — поиск не выходит за границы пользователя.
        data: Запрос, тип поиска и лимит.
        db: Сессия БД.

    Returns:
        Результаты поиска с повторённым запросом и метаданными.
    """
    service = MemorySearchService(db)
    results = await service.search(
        user_id=user_id,
        query=data.query,
        search_type=data.search_type,
        limit=data.limit,
    )

    return SearchResponse(
        query=results["query"],
        search_type=results["search_type"],
        results=[
            SearchResult(
                id=r["id"],
                type=r["type"],
                content=r.get("content", ""),
                score=r.get("score", 0),
                category=r.get("category"),
            )
            for r in results["results"]
        ],
        metadata=results["metadata"],
    )


@router.get("/users/{user_id}/stats")
async def get_memory_stats(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """
    Статистика памяти пользователя (счётчики по типам).

    Возвращает агрегаты из FactService.get_user_stats — без выгрузки самих
    фактов, поэтому эндпоинт дёшев и не раскрывает содержимое памяти.

    Args:
        user_id: Владелец памяти.
        db: Сессия БД.

    Returns:
        Словарь «тип факта -> количество».
    """
    service = FactService(db)
    return await service.get_user_stats(user_id)

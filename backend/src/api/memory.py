"""
Memory Router
API endpoints for memory operations
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
    """Fact creation schema — aligned with Fact model."""
    fact_type: str = Field(
        ...,
        description=f"One of: {', '.join(sorted(VALID_FACT_TYPES))}",
    )
    value: str = Field(..., description="Fact content text")
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    channel: str = Field(default="unknown", description="Source channel")


class FactResponse(BaseModel):
    """Fact response schema — aligned with Fact model."""
    id: str
    fact_type: str = Field(alias="type")
    value: str
    weight: float
    channel: str
    created_at: str
    is_superseded: bool

    model_config = {"populate_by_name": True}


class SearchRequest(BaseModel):
    """Search request schema."""
    query: str
    search_type: str = "hybrid"
    limit: int = 10


class SearchResult(BaseModel):
    """Search result schema."""
    id: str
    type: str
    content: str | dict
    score: float
    category: str | None = None


class SearchResponse(BaseModel):
    """Search response schema."""
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
    Store a new fact for user.

    Args:
        user_id: User identifier
        data: Fact data

    Returns:
        Created fact
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
    Get facts for user.

    Args:
        user_id: User identifier
        fact_type: Optional type filter
        limit: Maximum results

    Returns:
        List of facts
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
    Get fact by ID.

    Args:
        user_id: User identifier
        fact_id: Fact identifier

    Returns:
        Fact data

    Raises:
        404: Fact not found
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
    Delete fact (hard delete, used for Right to be Forgotten).

    Args:
        user_id: User identifier
        fact_id: Fact identifier

    Returns:
        Success message

    Raises:
        404: Fact not found
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
    Search user's memory.

    Args:
        user_id: User identifier
        data: Search request

    Returns:
        Search results
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
    Get memory statistics for user.

    Args:
        user_id: User identifier

    Returns:
        Statistics dict
    """
    service = FactService(db)
    return await service.get_user_stats(user_id)

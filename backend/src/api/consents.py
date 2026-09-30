"""
Роутер согласий: управление согласием на обработку данных (152-ФЗ).

Все эндпоинты требуют авторизации — управлять согласием может только сам
пользователь (через httpOnly-cookie с токеном доступа). B.3.2: помимо
grant/revoke есть отдельный явный эндпоинт полного удаления данных
(«право быть забытым»), а отзыв согласия автоматически запускает каскадное
удаление из всех хранилищ.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.schemas import ConsentGrant, ConsentResponse, UserResponse
from backend.src.services.auth_service import AuthService
from backend.src.services.consent_service import ConsentService
from backend.src.services.right_to_be_forgotten_service import (
    RightToBeForgottenService,
)

router = APIRouter(prefix="/consents", tags=["consents"])


async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Dependency: текущий пользователь из cookie с токеном доступа.

    FastAPI-зависимость, переиспользуемая всеми эндпоинтами роутера: читает
    токен из cookie (не из заголовка — так безопаснее при XSS), валидирует
    его через AuthService и отдаёт данные пользователя. Ошибки авторизации
    всегда 401, без раскрытия причины.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
        return UserResponse(
            id=user.id,
            phone_hash=user.phone_hash,
            created_at=user.created_at,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


class DataDeletionResponse(BaseModel):
    """Итог «права быть забытым»: что и откуда удалено.

    Счётчики по каждому хранилищу отдельно — пользователь видит прозрачный
    результат удаления, а не просто «ок»; user_deleted показывает, что удалён
    и сам аккаунт.
    """

    status: str
    postgres_facts_deleted: int
    qdrant_facts_deleted: int
    neo4j_facts_deleted: int
    user_deleted: bool


@router.post("/grant", response_model=ConsentResponse, status_code=201)
async def grant_consent(
    consent_data: ConsentGrant,
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Выдать согласие на обработку данных.

    ﻿201 (создан ресурс), а не 200 — согласие фиксируется как отдельная запись
    с каналом и IP (откуда получено), что требуется для аудита по 152-ФЗ.

    Args:
        consent_data: Данные согласия (канал, IP).
        current_user: Аутентифицированный пользователь.
        db: Сессия БД.

    Returns:
        Статус согласия после выдачи.

    Raises:
        400: Некорректные данные согласия.
    """
    service = ConsentService(db)
    try:
        await service.grant_consent(
            user_id=current_user.id,
            channel=consent_data.channel,
            ip_address=consent_data.ip_address,
        )
        status = await service.get_consent_status(current_user.id)
        return ConsentResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revoke", response_model=ConsentResponse)
async def revoke_consent(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Отозвать согласие — с каскадным удалением данных (B.3.2).

    Отзыв согласия теперь не просто флаг, а триггер полного удаления всех
    данных пользователя из PostgreSQL, Qdrant и Neo4j через
    RightToBeForgottenService: обработка без согласия запрещена 152-ФЗ,
    поэтому данные обязаны реально исчезнуть, а не остаться «в архиве».

    Args:
        current_user: Аутентифицированный пользователь.
        db: Сессия БД.

    Returns:
        Статус согласия после отзыва.

    Raises:
        400: Ошибка при отзыве согласия.
    """
    service = ConsentService(db)
    try:
        await service.revoke_consent(
            user_id=current_user.id,
            source="USER_REQUEST",
        )
        status = await service.get_consent_status(current_user.id)
        return ConsentResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=ConsentResponse)
async def get_consent_status(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Текущий статус согласия пользователя.

    Только чтение — не требует никаких изменений, поэтому GET. По статусу
    фронтенд решает, можно ли обрабатывать данные (например, включать память).

    Args:
        current_user: Аутентифицированный пользователь.
        db: Сессия БД.

    Returns:
        Текущий статус согласия.
    """
    service = ConsentService(db)
    status = await service.get_consent_status(current_user.id)
    return ConsentResponse(**status)


@router.post(
    "/data-deletion",
    response_model=DataDeletionResponse,
)
async def request_data_deletion(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> DataDeletionResponse:
    """
    Явный запрос «права быть забытым» (152-ФЗ).

    B.3.2: выделенный эндпоинт — пользователь может потребовать удаления
    данных, не отзывая согласие формально. Удаляет всё из PostgreSQL, Qdrant
    и Neo4j через RightToBeForgottenService и возвращает счётчики по каждому
    хранилищу. Отзыв согласия (/consents/revoke) запускает тот же процесс
    автоматически.

    Args:
        current_user: Аутентифицированный пользователь.
        db: Сессия БД.

    Returns:
        Сводка удаления: сколько фактов удалено из каждого хранилища.

    Raises:
        500: Сбой процесса удаления данных.
    """
    rtbf = RightToBeForgottenService(db)
    try:
        summary = await rtbf.delete_user_data(
            user_id=current_user.id,
            source="USER_REQUEST",
        )
        return DataDeletionResponse(
            status="deleted",
            postgres_facts_deleted=summary["postgres_facts_deleted"],
            qdrant_facts_deleted=summary["qdrant_facts_deleted"],
            neo4j_facts_deleted=summary["neo4j_facts_deleted"],
            user_deleted=summary["user_deleted"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data deletion failed: {e}",
        )

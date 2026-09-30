"""
Административный роутер управления привязками каналов.

Доступ — только для роли admin (@see get_current_admin). Позволяет видеть
все привязки, привязывать канал к пользователю и отвязывать его.

Почему административные эндпоинты, а не пользовательские: привязка канала
к конкретному человеку — чувствительная операция (идентификация клиента),
её должен выполнять оператор, а не сам клиент.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.dependencies import get_current_admin
from backend.src.models import ChannelBinding, User
from backend.src.services.channel_binding_service import ChannelBindingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/channels", tags=["admin-channels"])


class ChannelBindingResponse(BaseModel):
    """
    Представление привязки канала для админ-панели.

    Внешний идентификатор (`external_id`) — идентификатор клиента в канале
    (например, Telegram user id); флаг `is_active` отражает мягкую привязку
    (см. `ChannelBindingService`).
    """
    id: uuid.UUID
    user_id: uuid.UUID
    channel_type: str
    external_id: str
    is_active: bool


class ChannelBindRequest(BaseModel):
    """
    Запрос на создание привязки канала к пользователю.

    Валидация существования пользователя выполняется в эндпоинте
    `bind_channel` — схема отвечает только за формат запроса.
    """
    user_id: uuid.UUID
    channel_type: str
    external_id: str


@router.get("/", response_model=list[ChannelBindingResponse])
async def list_bindings(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelBindingResponse]:
    """
    Список всех привязок каналов (постранично).

    Используется для аудита: оператор видит, какие каналы привязаны к каким
    пользователям, что помогает выявить некорректные привязки.

    Args:
        skip: смещение от начала выборки
        limit: максимальное число записей на страницу

    Returns:
        list[ChannelBindingResponse]: привязки с внешними идентификаторами
    """
    result = await db.execute(
        select(ChannelBinding).offset(skip).limit(limit)
    )
    bindings = result.scalars().all()

    return [
        ChannelBindingResponse(
            id=binding.id,
            user_id=binding.user_id,
            channel_type=binding.channel_type,
            external_id=binding.external_id,
            is_active=binding.is_active,
        )
        for binding in bindings
    ]


@router.get("/user/{user_id}", response_model=list[ChannelBindingResponse])
async def get_user_channels(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelBindingResponse]:
    """
    Все привязки каналов конкретного пользователя.

    Показывает каналы, через которые клиент общается с системой, —
    базис для решения «по каким каналам продолжить диалог» (омниканальность).

    Args:
        user_id: UUID пользователя

    Returns:
        list[ChannelBindingResponse]: активные и неактивные привязки
    """
    service = ChannelBindingService(db)
    bindings = await service.get_user_channels(user_id)

    return [
        ChannelBindingResponse(
            id=binding.id,
            user_id=binding.user_id,
            channel_type=binding.channel_type,
            external_id=binding.external_id,
            is_active=binding.is_active,
        )
        for binding in bindings
    ]


@router.post("/", response_model=ChannelBindingResponse)
async def bind_channel(
    data: ChannelBindRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ChannelBindingResponse:
    """
    Привязка канала к пользователю.

    Сначала проверяется существование пользователя — привязка канала к
    несуществующему аккаунту создала бы «сиротскую» запись, на которую
    невозможно идентифицировать клиента. Сервис `ChannelBindingService`
    выполняет мягкую привязку (is_active).

    Args:
        data: user_id, channel_type, external_id

    Returns:
        ChannelBindingResponse: созданная привязка

    Raises:
        HTTPException: 404, если пользователь не найден
    """
    # Check user exists
    result = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = ChannelBindingService(db)
    binding = await service.bind_channel(
        user_id=data.user_id,
        channel_type=data.channel_type,
        external_id=data.external_id,
    )

    return ChannelBindingResponse(
        id=binding.id,
        user_id=binding.user_id,
        channel_type=binding.channel_type,
        external_id=binding.external_id,
        is_active=binding.is_active,
    )


@router.delete("/{binding_id}")
async def unbind_channel(
    binding_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Отвязка канала от пользователя.

    Удаление привязки означает, что входящие сообщения этого канала больше
    не будут связываться с данным пользователем — деактивация выполняется
    в `ChannelBindingService.unbind_channel` (мягкое удаление).

    Args:
        binding_id: UUID привязки

    Returns:
        {"status": "unbound"}

    Raises:
        HTTPException: 404, если привязка не найдена
    """
    result = await db.execute(
        select(ChannelBinding).where(ChannelBinding.id == binding_id)
    )
    binding = result.scalar_one_or_none()

    if not binding:
        raise HTTPException(status_code=404, detail="Binding not found")

    service = ChannelBindingService(db)
    await service.unbind_channel(
        channel_type=binding.channel_type,
        external_id=binding.external_id,
    )

    return {"status": "unbound"}

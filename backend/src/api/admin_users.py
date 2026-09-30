"""
Административный роутер управления пользователями.

Доступ — только для роли admin (@see get_current_admin): просмотр списка,
получение карточки, обновление роли/имени и удаление пользователя.

Ключевое решение: удаление (`delete_user`) выполняет физическое удаление
записи User — каскад по зависимым данным реализует процедура RTBF
(right to be forgotten), см. `RightToBeForgottenService`.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.dependencies import get_current_admin
from backend.src.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class UserResponse(BaseModel):
    """
    Карточка пользователя для админ-панели.

    Вместо номера телефона отдаётся только его HMAC-хеш (`phone_hash`) —
    сырой номер не покидает сервис аутентификации (см. `AuthService`):
    админу он не нужен, а раскрытие нарушило бы 152-ФЗ.
    """
    id: uuid.UUID
    phone_hash: str
    full_name: str | None
    role: str
    created_at: str


class UserUpdate(BaseModel):
    """
    Поля, допустимые для изменения администратором.

    Оба поля опциональны: обновляются только переданные. Роль и имя
    могут менять админы, но не сам пользователь (безопасность ролей).
    """
    full_name: str | None = None
    role: str | None = None


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """
    Список пользователей с постраничной выдачей.

    Ограничение `limit` (до 50 по умолчанию) защищает от выгрузки всей
    базы пользователей одним запросом; пагинация — offset/limit.

    Args:
        skip: смещение от начала выборки
        limit: максимальное число записей на страницу

    Returns:
        list[UserResponse]: карточки пользователей (без номеров телефонов)
    """
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return [
        UserResponse(
            id=user.id,
            phone_hash=user.phone_hash,
            full_name=user.full_name,
            role=user.role,
            created_at=user.created_at.isoformat(),
        )
        for user in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Карточка пользователя по идентификатору.

    Args:
        user_id: UUID пользователя

    Returns:
        UserResponse: данные пользователя

    Raises:
        HTTPException: 404, если пользователь не найден (не раскрываем
            разницу между «нет пользователя» и «нет доступа»)
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        phone_hash=user.phone_hash,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Обновление имени и/или роли пользователя.

    Меняются только переданные поля (`data` опционален), `flush()` отправляет
    изменения в БД в рамках текущей транзакции — commit выполняет middleware.

    Args:
        user_id: UUID пользователя
        data: новые значения full_name/role

    Returns:
        UserResponse: обновлённая карточка

    Raises:
        HTTPException: 404, если пользователь не найден
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role

    await db.flush()

    return UserResponse(
        id=user.id,
        phone_hash=user.phone_hash,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Удаление пользователя (право на забвение, 152-ФЗ).

    Физически удаляет запись User; каскад по связанным данным (факты,
    аудит, привязки каналов) — обязанность процедуры RTBF, которая
    вызывается отдельно через консенсус-пайплайн, а не здесь.

    Args:
        user_id: UUID пользователя

    Returns:
        {"status": "deleted"}

    Raises:
        HTTPException: 404, если пользователь не найден
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.flush()

    return {"status": "deleted"}

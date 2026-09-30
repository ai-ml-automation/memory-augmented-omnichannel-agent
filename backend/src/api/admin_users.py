"""
Users Router
Admin API for user management (requires admin role)
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
    """User response schema."""
    id: uuid.UUID
    phone_hash: str
    full_name: str | None
    role: str
    created_at: str


class UserUpdate(BaseModel):
    """User update schema."""
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
    List all users.

    Args:
        skip: Offset
        limit: Maximum number of users

    Returns:
        List of users
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
    Get user by ID.

    Args:
        user_id: User identifier

    Returns:
        User data

    Raises:
        404: User not found
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
    Update user.

    Args:
        user_id: User identifier
        data: Update data

    Returns:
        Updated user

    Raises:
        404: User not found
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
    Delete user.

    Args:
        user_id: User identifier

    Returns:
        Success message

    Raises:
        404: User not found
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

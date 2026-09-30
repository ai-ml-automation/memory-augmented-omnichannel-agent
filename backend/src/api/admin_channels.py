"""
Channels Router
Admin API for channel binding management (requires admin role)
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
    """Channel binding response schema."""
    id: uuid.UUID
    user_id: uuid.UUID
    channel_type: str
    external_id: str
    is_active: bool


class ChannelBindRequest(BaseModel):
    """Channel bind request schema."""
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
    List all channel bindings.

    Args:
        skip: Offset
        limit: Maximum number of bindings

    Returns:
        List of bindings
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
    Get all channels for user.

    Args:
        user_id: User identifier

    Returns:
        List of bindings
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
    Bind a channel to user.

    Args:
        data: Bind request

    Returns:
        Created binding

    Raises:
        404: User not found
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
    Unbind a channel.

    Args:
        binding_id: Binding identifier

    Returns:
        Success message

    Raises:
        404: Binding not found
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

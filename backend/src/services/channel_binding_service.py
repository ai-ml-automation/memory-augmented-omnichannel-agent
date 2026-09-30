"""
Channel Binding Service
Lookup and management of channel bindings for user identification
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import ChannelBinding, User


class ChannelBindingService:
    """Service for channel binding lookups and user identification."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_user_by_channel(
        self,
        channel_type: str,
        external_id: str,
    ) -> User | None:
        """
        Find user by channel type and external ID.

        Args:
            channel_type: Channel type (MAX, TG, VK, VOICE)
            external_id: External ID in the channel

        Returns:
            User if bound, None otherwise
        """
        result = await self.db.execute(
            select(User)
            .join(ChannelBinding)
            .where(
                ChannelBinding.channel_type == channel_type,
                ChannelBinding.external_id == external_id,
                ChannelBinding.is_active,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_channels(self, user_id: uuid.UUID) -> list[ChannelBinding]:
        """
        Get all active channels for user.

        Args:
            user_id: User identifier

        Returns:
            List of active ChannelBinding instances
        """
        result = await self.db.execute(
            select(ChannelBinding).where(
                ChannelBinding.user_id == user_id,
                ChannelBinding.is_active,
            )
        )
        return list(result.scalars().all())

    async def bind_channel(
        self,
        user_id: uuid.UUID,
        channel_type: str,
        external_id: str,
    ) -> ChannelBinding:
        """
        Bind a channel to user.

        Args:
            user_id: User identifier
            channel_type: Channel type
            external_id: External ID

        Returns:
            Created or updated ChannelBinding
        """
        # Check if binding already exists
        result = await self.db.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == channel_type,
                ChannelBinding.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.user_id == user_id:
                return existing
            # Bind to new user
            existing.user_id = user_id
            existing.is_active = True
            await self.db.flush()
            return existing

        # Create new binding
        binding = ChannelBinding(
            id=uuid.uuid4(),
            user_id=user_id,
            channel_type=channel_type,
            external_id=external_id,
            is_active=True,
        )
        self.db.add(binding)
        await self.db.flush()
        return binding

    async def unbind_channel(
        self,
        channel_type: str,
        external_id: str,
    ) -> bool:
        """
        Unbind a channel.

        Args:
            channel_type: Channel type
            external_id: External ID

        Returns:
            True if unbound, False if not found
        """
        result = await self.db.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == channel_type,
                ChannelBinding.external_id == external_id,
            )
        )
        binding = result.scalar_one_or_none()

        if not binding:
            return False

        binding.is_active = False
        await self.db.flush()
        return True

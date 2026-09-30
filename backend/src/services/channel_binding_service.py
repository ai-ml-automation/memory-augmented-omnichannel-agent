"""
Сервис привязки каналов для идентификации пользователя.

Связывает внешний ID в канале (MAX, TG, VK, VOICE) с внутренним user_id:
входящее сообщение из канала однозначно отображается на пользователя.
Привязка мягкая — is_active=False, запись сохраняется для истории.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import ChannelBinding, User


class ChannelBindingService:
    """
    Сервис привязок: поиск пользователя по каналу, связывание/отвязка.

    Поиск идёт только по активным привязкам (is_active=True): отвязанный
    канал не должен идентифицировать пользователя (152-ФЗ, отзыв согласия).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_user_by_channel(
        self,
        channel_type: str,
        external_id: str,
    ) -> User | None:
        """
        Поиск пользователя по каналу и внешнему ID.

        JOIN с ChannelBinding и фильтр is_active: учитываются только привязки,
        по которым канал реально идентифицирует пользователя.
        Args:
            channel_type: канал (MAX, TG, VK, VOICE)
            external_id: внешний ID в канале
        Returns:
            User или None
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
        Активные каналы пользователя.

        Отвязанные каналы не возвращаются: они не должны использоваться
        для идентификации после отзыва согласия (152-ФЗ).
        Args:
            user_id: идентификатор пользователя
        Returns:
            список активных ChannelBinding
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
        Привязка канала к пользователю (идемпотентно).

        Существующая привязка: возвращается как есть (свой пользователь)
        или переключается на нового — канал принадлежит одному пользователю.
        Args:
            user_id: идентификатор пользователя
            channel_type: канал (MAX, TG, VK, VOICE)
            external_id: внешний ID в канале
        Returns:
            созданная или обновлённая ChannelBinding
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
        Отвязка канала: is_active=False (запись сохраняется).

        Мягкое удаление вместо физического: сохраняет аудит-след и позволяет
        повторно привязать канал без потери истории (B.3.2).
        Args:
            channel_type: канал (MAX, TG, VK, VOICE)
            external_id: внешний ID в канале
        Returns:
            True если отвязан, False если привязка не найдена
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

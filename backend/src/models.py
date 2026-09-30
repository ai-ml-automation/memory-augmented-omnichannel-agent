"""
SQLAlchemy-модели системы памяти омниканального агента.

Все модели сосредоточены в одном файле по требованию CODING_STANDARDS.md:
это упрощает обзор схемы БД и миграции, цена — больший файл.

Ключевые решения:
- телефон хранится только в виде хэша (phone_hash) — минимизация ПДн (152-ФЗ);
- связи User → Consent/ChannelBinding/Session/Fact/AuditLog каскадные:
  удаление пользователя удаляет все его данные (право на забвение);
- JSONB-колонка context_json позволяет менять структуру без миграций.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.database import Base


class User(Base):
    """
    Пользователь системы — владелец памяти, согласий и привязок каналов.

    Создаётся при регистрации, удаляется каскадом со всеми данными по
    запросу «право на забвение» (152-ФЗ).

    Ключевые поля: phone_hash (хэш телефона вместо открытого номера),
    role (user/operator/admin — доступ к админ-эндпоинтам),
    jwt_version (инкремент инвалидирует старые JWT-токены).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), default="user"
    )  # user, operator, admin
    jwt_version: Mapped[int] = mapped_column(Integer, default=1)  # смена инвалидирует старые JWT
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)

    # Relationships
    consents: Mapped[list["Consent"]] = relationship(
        "Consent", back_populates="user", cascade="all, delete-orphan"
    )
    channel_bindings: Mapped[list["ChannelBinding"]] = relationship(
        "ChannelBinding", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    facts: Mapped[list["Fact"]] = relationship(
        "Fact", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )


class Consent(Base):
    """
    Согласие пользователя на обработку данных по каналу (152-ФЗ).

    Хранит историю grant/revoke, а не перезаписывает: revoked_at
    фиксирует отзыв, новая запись создаётся при повторном согласии.

    Ключевые поля: channel (MAX/TG/VK/VOICE), ip_address (адрес, с
    которого дано согласие), granted_at/revoked_at (период действия).
    """

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(50))
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="consents")


class ChannelBinding(Base):
    """
    Привязка внешнего канала (MAX, TG, VK, VOICE) к пользователю.

    Позволяет маршрутизировать сообщения из мессенджеров в сессию
    нужного пользователя (омниканальность) и ограничивать число каналов.

    Ключевые поля: channel_type (тип канала), external_id (идентификатор
    собеседника в канале — telegram chat_id, vk user_id и т.п.).
    """

    __tablename__ = "channel_bindings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    channel_type: Mapped[str] = mapped_column(
        String(20), index=True
    )  # MAX, TG, VK, VOICE
    external_id: Mapped[str] = mapped_column(String(255), index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="channel_bindings")


class Session(Base):
    """
    Сессия взаимодействия пользователя с агентом в одном канале.

    Одна сессия объединяет последовательность сообщений и хранит
    контекст разговора (context_json) для непрерывности диалога.

    Ключевые поля: channel_type, started_at/ended_at (открыта/закрыта),
    context_json (JSONB — гибкий контекст без миграций).
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    channel_type: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")


class Fact(Base):
    """
    Факт о пользователе — единица долговременной памяти агента.

    Извлекается из сообщений, персонализирует ответы; weight и expires_at
    реализуют затухание памяти, is_superseded отмечает замещение факта.

    Ключевые поля: type (intent/preference/complaint/agreement/rejection/
    personal_info), weight (важность), expires_at (устаревание).
    """

    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    type: Mapped[str] = mapped_column(
        String(20), index=True
    )  # intent, preference, complaint, agreement, rejection, personal_info
    value: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    channel: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)  # True = факт замещён более актуальным

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="facts")
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="fact"
    )


class AuditLog(Base):
    """
    Журнал аудита доступа к данным (152-ФЗ).

    Каждое действие чтения/записи/удаления фактов фиксируется для
    доказуемости обработки; данные маскируются на уровне логирования.

    Ключевые поля: action (READ/WRITE/DELETE), source (AI/OPERATOR),
    fact_id (опциональная ссылка на факт), ip_address (инициатор).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(20))  # READ, WRITE, DELETE
    fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facts.id"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    source: Mapped[str] = mapped_column(String(20))  # AI, OPERATOR
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="audit_logs")
    fact: Mapped["Fact | None"] = relationship("Fact", back_populates="audit_logs")

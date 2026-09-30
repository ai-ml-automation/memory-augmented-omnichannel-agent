"""Начальная схема БД: все 6 таблиц ядра приложения.

Создаёт users, consents (152-ФЗ), channel_bindings, sessions, facts (память),
audit_logs (журнал 152-ФЗ). Поля фактов хранятся в открытом виде, т.к. шифрование
реализовано на уровне приложения (AES-256-GCM), а не в схеме.

Revision ID: 001_initial | Revises: (первая миграция) | Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Создание таблиц начальной схемы в порядке зависимостей.

    Порядок важен: consents/channel_bindings/sessions/facts ссылаются на users,
    audit_logs — на users и facts, поэтому родительские таблицы создаются первыми.
    """
    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('phone_hash', sa.String(64), unique=True, index=True),
        sa.Column('password_hash', sa.String(128)),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(20), server_default='user'),
        sa.Column('jwt_version', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('tenant_id', sa.String(64), index=True),
    )

    # Consents table (152-FZ)
    op.create_table(
        'consents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), index=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('channel', sa.String(50)),
        sa.Column('ip_address', sa.String(45), nullable=True),
    )

    # Channel bindings table
    op.create_table(
        'channel_bindings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), index=True),
        sa.Column('channel_type', sa.String(20), index=True),
        sa.Column('external_id', sa.String(255), index=True),
    )

    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), index=True),
        sa.Column('channel_type', sa.String(20)),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('context_json', JSONB, nullable=True),
    )

    # Facts table (memory storage)
    op.create_table(
        'facts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), index=True),
        sa.Column('type', sa.String(20), index=True),
        sa.Column('value', sa.Text),
        sa.Column('weight', sa.Float, server_default='1.0'),
        sa.Column('channel', sa.String(20)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_superseded', sa.Boolean, server_default='false'),
        sa.Column('encrypted_data', sa.Text, nullable=True),
    )

    # Audit logs table (152-FZ compliance)
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), index=True),
        sa.Column('action', sa.String(20)),
        sa.Column('fact_id', UUID(as_uuid=True), sa.ForeignKey('facts.id'), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('source', sa.String(20)),
        sa.Column('ip_address', sa.String(45), nullable=True),
    )


def downgrade() -> None:
    """
    Удаление всех таблиц в обратном порядке (сначала зависимые).

    Обратный порядок обязателен из-за внешних ключей: audit_logs → facts → users.
    """
    op.drop_table('audit_logs')
    op.drop_table('facts')
    op.drop_table('sessions')
    op.drop_table('channel_bindings')
    op.drop_table('consents')
    op.drop_table('users')
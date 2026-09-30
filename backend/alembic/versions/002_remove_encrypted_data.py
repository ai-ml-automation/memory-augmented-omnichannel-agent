"""Удаление мёртвого поля encrypted_data из таблицы facts (Phase δ).

Поле добавлено в 001 как «сырое» хранилище зашифрованного значения, но после
решения шифровать сам факт на уровне приложения (AES-256-GCM, поле value)
отдельная колонка стала дублирующей и удалена (см. docs/new/ARCHITECTURE.md).

Revision ID: 002 | Revises: 001_initial_schema | Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Удаление колонки encrypted_data из facts.

    Операция необратима по данным, но колонка к моменту миграции уже не
    заполнялась (мёртвое поле) — потеря данных отсутствует.
    """
    op.drop_column("facts", "encrypted_data")


def downgrade() -> None:
    """
    Восстановление колонки encrypted_data (nullable) для отката миграции.

    Данные не восстанавливаются — колонка создаётся пустой; это допустимо,
    т.к. поле было мёртвым и не содержало значимых данных.
    """
    op.add_column(
        "facts",
        sa.Column("encrypted_data", sa.Text(), nullable=True),
    )

"""remove unused encrypted_data column from facts

Revision ID: 002
Revises: 001_initial_schema
Create Date: 2026-07-15

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove unused encrypted_data column from facts table."""
    op.drop_column("facts", "encrypted_data")


def downgrade() -> None:
    """Add encrypted_data column back to facts table."""
    op.add_column(
        "facts",
        sa.Column("encrypted_data", sa.Text(), nullable=True),
    )

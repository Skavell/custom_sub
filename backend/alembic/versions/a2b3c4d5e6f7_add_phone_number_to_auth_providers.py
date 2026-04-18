"""add phone_number to auth_providers

Revision ID: a2b3c4d5e6f7
Revises: 64938a85a3cd
Create Date: 2026-04-18 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "64938a85a3cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("auth_providers", sa.Column("phone_number", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_providers", "phone_number")

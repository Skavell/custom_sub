"""add numeric Remnawave v3 user id

Revision ID: b7c8d9e0f1a2
Revises: 4e95ce49b31d
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "4e95ce49b31d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("remnawave_user_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint("uq_users_remnawave_user_id", "users", ["remnawave_user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_remnawave_user_id", "users", type_="unique")
    op.drop_column("users", "remnawave_user_id")

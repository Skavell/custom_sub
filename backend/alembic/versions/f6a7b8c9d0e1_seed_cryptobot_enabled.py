"""seed cryptobot_enabled setting

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-07 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO settings (key, value, is_sensitive) "
            "VALUES (:key, CAST(:value AS jsonb), :is_sensitive) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"key": "cryptobot_enabled", "value": json.dumps({"value": "true"}), "is_sensitive": False},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = 'cryptobot_enabled'"),
    )

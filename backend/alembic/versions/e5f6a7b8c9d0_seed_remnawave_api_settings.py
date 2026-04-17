"""seed remnawave api settings (url and token)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-06 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    ("remnawave_url", "", False),
    ("remnawave_token", "", True),
]


def upgrade() -> None:
    conn = op.get_bind()
    for key, value, is_sensitive in _SETTINGS:
        conn.execute(
            sa.text(
                "INSERT INTO settings (key, value, is_sensitive) "
                "VALUES (:key, CAST(:value AS jsonb), :is_sensitive) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key, "value": json.dumps({"value": value}), "is_sensitive": is_sensitive},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key, _, _ in _SETTINGS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )

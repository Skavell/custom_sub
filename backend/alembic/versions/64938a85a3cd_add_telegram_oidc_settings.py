"""add telegram oidc settings

Revision ID: 64938a85a3cd
Revises: f6a7b8c9d0e1
Create Date: 2026-04-18 16:13:52.696860

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '64938a85a3cd'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    ("telegram_oidc_enabled", "false", False),
    ("telegram_oidc_client_id", "", False),
    ("telegram_oidc_client_secret", "", False),
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

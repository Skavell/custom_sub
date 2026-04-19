"""seed remnawave_webhook_secret setting

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-19 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
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
        {"key": "remnawave_webhook_secret", "value": json.dumps({"value": ""}), "is_sensitive": False},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = :key"),
        {"key": "remnawave_webhook_secret"},
    )

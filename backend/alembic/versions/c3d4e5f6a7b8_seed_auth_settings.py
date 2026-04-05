"""seed auth and remnawave settings

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-05 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    ("registration_enabled", "true", False),
    ("email_verification_enabled", "false", False),
    (
        "allowed_email_domains",
        "gmail.com,mail.ru,yandex.ru,yahoo.com,outlook.com,hotmail.com,icloud.com,rambler.ru,bk.ru,list.ru,inbox.ru,proton.me,protonmail.com,me.com,live.com",
        False,
    ),
    ("resend_api_key", "", True),
    ("email_from_address", "", False),
    ("email_from_name", "", False),
    ("remnawave_trial_squad_uuids", "", False),
    ("remnawave_paid_squad_uuids", "", False),
]


def upgrade() -> None:
    conn = op.get_bind()
    for key, value, is_sensitive in _SETTINGS:
        conn.execute(
            sa.text(
                "INSERT INTO settings (key, value, is_sensitive) "
                "VALUES (:key, :value, :is_sensitive) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key, "value": json.dumps({"value": value}), "is_sensitive": is_sensitive},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [k for k, _, _ in _SETTINGS]
    for key in keys:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )

"""refactor squad settings: split trial/paid into internal/external

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-06 00:00:00.000000

"""
import json
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_SETTINGS = [
    ("remnawave_trial_internal_squad_uuids", "", False),
    ("remnawave_trial_external_squad_uuids", "", False),
    ("remnawave_paid_internal_squad_uuids", "", False),
    ("remnawave_paid_external_squad_uuids", "", False),
]

_OLD_KEYS = [
    "remnawave_trial_squad_uuids",
    "remnawave_paid_squad_uuids",
]


def upgrade() -> None:
    conn = op.get_bind()

    # Migrate existing values: copy trial UUIDs → trial_internal, paid UUIDs → paid_internal
    for old_key, new_key in [
        ("remnawave_trial_squad_uuids", "remnawave_trial_internal_squad_uuids"),
        ("remnawave_paid_squad_uuids", "remnawave_paid_internal_squad_uuids"),
    ]:
        row = conn.execute(
            sa.text("SELECT value FROM settings WHERE key = :key"),
            {"key": old_key},
        ).fetchone()
        if row is not None:
            # row[0] is a dict (JSONB parsed by asyncpg) — must serialize back to JSON string
            raw_value = row[0] if isinstance(row[0], str) else json.dumps(row[0])
            conn.execute(
                sa.text(
                    "INSERT INTO settings (key, value, is_sensitive) "
                    "VALUES (:key, CAST(:value AS jsonb), false) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"key": new_key, "value": raw_value},
            )

    # Insert remaining new keys (external ones) with empty defaults
    for key in ["remnawave_trial_external_squad_uuids", "remnawave_paid_external_squad_uuids"]:
        conn.execute(
            sa.text(
                "INSERT INTO settings (key, value, is_sensitive) "
                "VALUES (:key, CAST(:value AS jsonb), false) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key, "value": json.dumps({"value": ""})},
        )

    # Remove old keys
    for key in _OLD_KEYS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Restore old keys from internal values
    for new_key, old_key in [
        ("remnawave_trial_internal_squad_uuids", "remnawave_trial_squad_uuids"),
        ("remnawave_paid_internal_squad_uuids", "remnawave_paid_squad_uuids"),
    ]:
        row = conn.execute(
            sa.text("SELECT value FROM settings WHERE key = :key"),
            {"key": new_key},
        ).fetchone()
        if row is not None:
            raw_value = row[0] if isinstance(row[0], str) else json.dumps(row[0])
        else:
            raw_value = json.dumps({"value": ""})
        conn.execute(
            sa.text(
                "INSERT INTO settings (key, value, is_sensitive) "
                "VALUES (:key, CAST(:value AS jsonb), false) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"key": old_key, "value": raw_value},
        )

    # Remove new keys
    for key, _, _ in _NEW_SETTINGS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )

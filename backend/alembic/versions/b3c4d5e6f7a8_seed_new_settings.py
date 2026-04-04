"""seed_new_settings

Revision ID: b3c4d5e6f7a8
Revises: 1e776950ed0d
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = '1e776950ed0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SETTINGS = [
    # OAuth / identity
    ("telegram_bot_username", "", False),
    ("site_name", "Skavellion VPN", False),
    ("support_telegram_link", "", False),
    # Install page — Android
    ("install_android_app_name", "FlClash", False),
    ("install_android_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — iOS
    ("install_ios_app_name", "Clash Mi", False),
    ("install_ios_store_url", "https://apps.apple.com/app/clash-mi/id1574653991", False),
    # Install page — Windows
    ("install_windows_app_name", "FlClash", False),
    ("install_windows_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — macOS
    ("install_macos_app_name", "FlClash", False),
    ("install_macos_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
    # Install page — Linux
    ("install_linux_app_name", "FlClash", False),
    ("install_linux_store_url", "https://github.com/chen08209/FlClash/releases/latest", False),
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
            {"key": key, "value": value, "is_sensitive": is_sensitive},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [k for k, _, _ in _SETTINGS]
    for key in keys:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )

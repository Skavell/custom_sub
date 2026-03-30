"""seed_usdt_exchange_rate

Revision ID: 291527ff2561
Revises: 1a19e8da3d6b
Create Date: 2026-03-30 13:22:33.292621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '291527ff2561'
down_revision: Union[str, Sequence[str], None] = '1a19e8da3d6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        INSERT INTO settings (key, value, is_sensitive)
        VALUES ('usdt_exchange_rate', '{"value": "83"}', false)
        ON CONFLICT (key) DO NOTHING
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM settings WHERE key = 'usdt_exchange_rate'")
    )

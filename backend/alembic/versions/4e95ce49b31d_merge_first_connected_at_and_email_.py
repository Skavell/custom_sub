"""merge first_connected_at and email_verification heads

Revision ID: 4e95ce49b31d
Revises: 744b110fd9e1, d2e3f4a5b6c7
Create Date: 2026-04-20 02:15:40.823791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e95ce49b31d'
down_revision: Union[str, Sequence[str], None] = ('744b110fd9e1', 'd2e3f4a5b6c7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

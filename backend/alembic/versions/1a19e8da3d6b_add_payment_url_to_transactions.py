"""add_payment_url_to_transactions

Revision ID: 1a19e8da3d6b
Revises: f989da77bf10
Create Date: 2026-03-30 05:52:26.701579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a19e8da3d6b'
down_revision: Union[str, Sequence[str], None] = 'f989da77bf10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("payment_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "payment_url")

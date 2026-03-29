"""seed_plans

Revision ID: f989da77bf10
Revises: e7cbe1ed933e
Create Date: 2026-03-29 20:16:10.987057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = 'f989da77bf10'
down_revision: Union[str, Sequence[str], None] = 'e7cbe1ed933e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        INSERT INTO plans (id, name, label, duration_days, price_rub, new_user_price_rub, is_active, sort_order)
        VALUES
            (:id1, '1_month',   '1 месяц',   30,  200, 100, true, 1),
            (:id2, '3_months',  '3 месяца',  90,  590, NULL, true, 2),
            (:id3, '6_months',  '6 месяцев', 180, 1100, NULL, true, 3),
            (:id4, '12_months', '1 год',     365, 2000, NULL, true, 4)
        ON CONFLICT (name) DO NOTHING
        """),
        {
            "id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()), "id4": str(uuid.uuid4()),
        }
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM plans WHERE name IN ('1_month','3_months','6_months','12_months')"))

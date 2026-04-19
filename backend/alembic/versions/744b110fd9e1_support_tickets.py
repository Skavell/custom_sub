"""support_tickets

Revision ID: 744b110fd9e1
Revises: a2b3c4d5e6f7
Create Date: 2026-04-19 14:01:04.425045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '744b110fd9e1'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создать sequence для номеров обращений
    op.execute("CREATE SEQUENCE support_ticket_number_seq START 1")

    # 2. Создать таблицу support_tickets
    op.create_table(
        'support_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('number', sa.Integer(), sa.Sequence('support_ticket_number_seq'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('number'),
    )

    # 3. Мигрировать старые support_messages в тикеты
    op.execute("""
        WITH ranked AS (
            SELECT
                id AS msg_id,
                user_id,
                message,
                created_at,
                ROW_NUMBER() OVER (ORDER BY created_at, id) AS rn
            FROM support_messages
        )
        INSERT INTO support_tickets (id, number, user_id, subject, status, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            nextval('support_ticket_number_seq'),
            user_id,
            LEFT(message, 50) || CASE WHEN length(message) > 50 THEN '...' ELSE '' END,
            'closed',
            created_at,
            created_at
        FROM ranked
        ORDER BY rn
    """)

    # 4. Добавить новые колонки в support_messages (пока nullable для обратной совместимости)
    op.add_column('support_messages', sa.Column('ticket_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('support_messages', sa.Column('author_type', sa.String(10), nullable=True))
    op.add_column('support_messages', sa.Column('text', sa.Text(), nullable=True))
    op.add_column('support_messages', sa.Column('is_read_by_user', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('support_messages', sa.Column('telegram_message_id', sa.BigInteger(), nullable=True))

    # 5. Связать каждое сообщение с его тикетом
    op.execute("""
        WITH ranked_msgs AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS rn
            FROM support_messages
        ),
        ranked_tickets AS (
            SELECT id AS ticket_id, number, ROW_NUMBER() OVER (ORDER BY number) AS rn
            FROM support_tickets
            WHERE status = 'closed'
        )
        UPDATE support_messages sm
        SET
            ticket_id = rt.ticket_id,
            author_type = 'user',
            text = sm.message,
            is_read_by_user = true
        FROM ranked_msgs rm
        JOIN ranked_tickets rt ON rm.rn = rt.rn
        WHERE sm.id = rm.id
    """)

    # 6. Сделать обязательные колонки NOT NULL и добавить FK
    op.alter_column('support_messages', 'ticket_id', nullable=False)
    op.alter_column('support_messages', 'author_type', nullable=False)
    op.alter_column('support_messages', 'text', nullable=False)
    op.alter_column('support_messages', 'is_read_by_user', nullable=False)
    op.drop_constraint('support_messages_user_id_fkey', 'support_messages', type_='foreignkey')
    op.create_foreign_key(None, 'support_messages', 'support_tickets', ['ticket_id'], ['id'], ondelete='CASCADE')

    # 7. Удалить старые колонки
    op.drop_column('support_messages', 'display_name')
    op.drop_column('support_messages', 'message')
    op.drop_column('support_messages', 'user_id')


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for this migration")

"""drop_role_add_plan

Revision ID: dedf3a08f66d
Revises: 240957cf6102
Create Date: 2026-06-04 15:53:43.103524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dedf3a08f66d'
down_revision: Union[str, None] = '240957cf6102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table is required for SQLite column drops/adds on existing tables.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('plan', sa.String(length=20), nullable=False, server_default='free')
        )
        batch_op.drop_column('role')


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'role',
                sa.Enum('MANAGER', 'BUYER', name='userrole'),
                nullable=False,
                server_default='buyer',
            )
        )
        batch_op.drop_column('plan')

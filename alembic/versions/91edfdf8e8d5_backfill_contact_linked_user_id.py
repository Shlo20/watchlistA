"""backfill_contact_linked_user_id

Revision ID: 91edfdf8e8d5
Revises: 2cea0b86afca
Create Date: 2026-06-15 04:16:00.261756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91edfdf8e8d5'
down_revision: Union[str, None] = '2cea0b86afca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # For each contact where linked_user_id is still null, resolve it from the users table.
    # Safe to re-run: the WHERE linked_user_id IS NULL guard makes it idempotent.
    op.execute(
        """
        UPDATE contacts
        SET linked_user_id = (
            SELECT id FROM users WHERE phone = contacts.phone LIMIT 1
        )
        WHERE linked_user_id IS NULL
          AND EXISTS (SELECT 1 FROM users WHERE phone = contacts.phone)
        """
    )


def downgrade() -> None:
    pass  # data-only migration; downgrade is a no-op

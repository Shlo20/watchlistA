"""backfill_list_titles

Revision ID: 1c075982a8b1
Revises: 91edfdf8e8d5
Create Date: 2026-06-15 16:25:08.768722

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c075982a8b1'
down_revision: Union[str, None] = '91edfdf8e8d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _title_from_dt(created_at_str) -> str:
    """Generate 'Restock — Mon D' from a stored datetime string."""
    date_part = (created_at_str or "")[:10]  # "YYYY-MM-DD"
    try:
        dt = datetime.strptime(date_part, "%Y-%m-%d")
    except Exception:
        dt = datetime.utcnow()
    return f"Restock — {dt.strftime('%b')} {dt.day}"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, created_at FROM lists "
            "WHERE title IS NULL OR title = '' OR title = 'Untitled list'"
        )
    ).fetchall()
    for row_id, created_at_str in rows:
        title = _title_from_dt(created_at_str)
        conn.execute(
            sa.text("UPDATE lists SET title = :title WHERE id = :id"),
            {"title": title, "id": row_id},
        )


def downgrade() -> None:
    # Backfill is idempotent and non-destructive; no meaningful undo.
    pass

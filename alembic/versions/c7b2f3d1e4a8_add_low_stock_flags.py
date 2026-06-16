"""add low_stock_flags table

Revision ID: c7b2f3d1e4a8
Revises: 1ba6aca714fe
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa

revision = 'c7b2f3d1e4a8'
down_revision = '1ba6aca714fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "low_stock_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_low_stock_user_product"),
    )
    op.create_index("ix_low_stock_flags_user_id", "low_stock_flags", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_low_stock_flags_user_id", table_name="low_stock_flags")
    op.drop_table("low_stock_flags")

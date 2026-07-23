"""personal catalog

Revision ID: c4a9f0821d33
Revises: b7f6e23d9a11
Create Date: 2026-07-20 21:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a9f0821d33"
down_revision: Union[str, Sequence[str], None] = "b7f6e23d9a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_catalog_items",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("department_id", sa.SmallInteger(), nullable=False),
        sa.Column("default_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("default_unit", sa.String(length=16), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("default_quantity > 0", name=op.f("ck_user_catalog_items_positive_default_quantity")),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name=op.f("fk_user_catalog_items_department_id_departments"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_catalog_items_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_catalog_items")),
        sa.UniqueConstraint("user_id", "normalized_name", name=op.f("uq_user_catalog_items_user_id")),
    )
    op.create_index(op.f("ix_user_catalog_items_user_id"), "user_catalog_items", ["user_id"], unique=False)
    op.execute(
        """
        UPDATE products
        SET department_id = (SELECT id FROM departments WHERE code = 'fish_seafood')
        WHERE normalized_name IN ('филе лосося', 'треска', 'креветки', 'скумбрия')
        """
    )


def downgrade() -> None:
    op.drop_table("user_catalog_items")

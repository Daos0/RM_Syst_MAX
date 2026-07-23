"""per-user pinned shopping lists

Revision ID: a82d1c7f4e90
Revises: f14c8a9d22b1
Create Date: 2026-07-21 15:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a82d1c7f4e90"
down_revision: Union[str, Sequence[str], None] = "f14c8a9d22b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_list_pins",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "list_id"),
    )
    op.create_index("ix_user_list_pins_list_id", "user_list_pins", ["list_id"])
    op.create_index("ix_user_list_pins_user_id", "user_list_pins", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_list_pins")

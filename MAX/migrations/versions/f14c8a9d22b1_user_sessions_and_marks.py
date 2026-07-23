"""user sessions and shopping item marks

Revision ID: f14c8a9d22b1
Revises: c4a9f0821d33
Create Date: 2026-07-21 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f14c8a9d22b1"
down_revision: Union[str, Sequence[str], None] = "c4a9f0821d33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.add_column(
        "shopping_items",
        sa.Column("mark", sa.String(length=16), server_default="", nullable=False),
    )
    op.create_check_constraint(
        "ck_shopping_items_valid_mark",
        "shopping_items",
        "mark IN ('', 'blue', 'amber', 'violet', 'coral')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_shopping_items_valid_mark", "shopping_items", type_="check")
    op.drop_column("shopping_items", "mark")
    op.drop_table("user_sessions")

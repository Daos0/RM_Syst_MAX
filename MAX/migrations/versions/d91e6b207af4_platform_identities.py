"""add messenger-neutral user identities

Revision ID: d91e6b207af4
Revises: a82d1c7f4e90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d91e6b207af4"
down_revision: Union[str, Sequence[str], None] = "a82d1c7f4e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "max_user_id", existing_type=sa.String(64), nullable=True)
    op.create_table(
        "user_identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_user_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("locale", sa.String(length=12), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "provider IN ('max', 'telegram')",
            name="ck_user_identities_valid_identity_provider",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id"),
        sa.UniqueConstraint("user_id", "provider"),
    )
    op.create_index(
        "ix_user_identities_user_id", "user_identities", ["user_id"], unique=False
    )
    op.execute(
        """
        INSERT INTO user_identities (
            id, user_id, provider, provider_user_id, username,
            display_name, avatar_url, locale, created_at, updated_at
        )
        SELECT gen_random_uuid(), id, 'max', max_user_id, username,
               display_name, avatar_url, locale, created_at, updated_at
        FROM users
        WHERE max_user_id IS NOT NULL
        ON CONFLICT (provider, provider_user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE max_user_id IS NULL")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.alter_column("users", "max_user_id", existing_type=sa.String(64), nullable=False)

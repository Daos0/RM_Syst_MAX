"""bot audience activity and broadcast queue

Revision ID: c38f9a610b22
Revises: d91e6b207af4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c38f9a610b22"
down_revision: Union[str, Sequence[str], None] = "d91e6b207af4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_identities",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("UPDATE user_identities SET last_seen_at = updated_at")
    op.create_index(
        "ix_user_identities_last_seen_at",
        "user_identities",
        ["last_seen_at"],
        unique=False,
    )
    op.create_table(
        "broadcast_campaigns",
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "provider IN ('max', 'telegram')",
            name="ck_broadcast_campaigns_valid_broadcast_provider",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'cancelled', 'failed')",
            name="ck_broadcast_campaigns_valid_broadcast_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcast_campaigns_provider", "broadcast_campaigns", ["provider"], unique=False)
    op.create_index("ix_broadcast_campaigns_status", "broadcast_campaigns", ["status"], unique=False)
    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("provider_user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed', 'skipped')",
            name="ck_broadcast_recipients_valid_broadcast_recipient_status",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["broadcast_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_id"], ["user_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "identity_id"),
    )
    op.create_index(
        "ix_broadcast_recipients_claim",
        "broadcast_recipients",
        ["status", "campaign_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_broadcast_recipients_claim", table_name="broadcast_recipients")
    op.drop_table("broadcast_recipients")
    op.drop_index("ix_broadcast_campaigns_status", table_name="broadcast_campaigns")
    op.drop_index("ix_broadcast_campaigns_provider", table_name="broadcast_campaigns")
    op.drop_table("broadcast_campaigns")
    op.drop_index("ix_user_identities_last_seen_at", table_name="user_identities")
    op.drop_column("user_identities", "last_seen_at")

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.catalog import Department, Product
from app.db.models.identity import Space, SpaceMember


class ListTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "list_templates"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    space_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class TemplateItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "template_items"
    __table_args__ = (UniqueConstraint("template_id", "product_id"),)

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("list_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ShoppingList(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shopping_lists"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'archived')", name="valid_status"
        ),
        CheckConstraint(
            "category IN ('personal', 'family', 'shared')", name="valid_category"
        ),
    )

    space_id: Mapped[UUID] = mapped_column(
        ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("list_templates.id", ondelete="SET NULL"), nullable=True
    )
    created_by_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("space_members.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(
        String(24), nullable=False, default="personal", server_default="personal"
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    space: Mapped[Space] = relationship()


class UserListPin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_list_pins"
    __table_args__ = (UniqueConstraint("user_id", "list_id"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    list_id: Mapped[UUID] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )


class ShoppingItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shopping_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint(
            "status IN ('active', 'assigned', 'purchased', 'unavailable')",
            name="valid_status",
        ),
        Index(
            "uq_shopping_items_active_dedupe",
            "list_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    list_id: Mapped[UUID] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("space_members.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("space_members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchased_by_member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("space_members.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(220), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    purchased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    product: Mapped[Product | None] = relationship()
    department: Mapped[Department] = relationship()


class SectionAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "section_assignments"
    __table_args__ = (UniqueConstraint("list_id", "department_id"),)

    list_id: Mapped[UUID] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("space_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

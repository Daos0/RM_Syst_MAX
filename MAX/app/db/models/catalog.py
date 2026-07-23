from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class CatalogCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "catalog_categories"
    __table_args__ = (
        CheckConstraint("kind IN ('product', 'dish', 'supply')", name="valid_kind"),
        UniqueConstraint("kind", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("catalog_kind IN ('product', 'supply')", name="valid_catalog_kind"),
        Index(
            "ix_products_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ),
    )

    normalized_name: Mapped[str] = mapped_column(
        String(180), nullable=False, unique=True
    )
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    catalog_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    catalog_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="product")
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="🛒")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    catalog_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_quantity: Mapped[float] = mapped_column(
        Numeric(12, 3), nullable=False, default=1
    )
    default_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="шт.")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    department: Mapped[Department] = relationship()
    catalog_category: Mapped[CatalogCategory | None] = relationship()


class ProductAlias(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        Index(
            "ix_product_aliases_name_trgm",
            "normalized_alias",
            postgresql_using="gin",
            postgresql_ops={"normalized_alias": "gin_trgm_ops"},
        ),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(
        String(180), nullable=False, unique=True, index=True
    )

    product: Mapped[Product] = relationship()


class UserCatalogItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_catalog_items"
    __table_args__ = (
        CheckConstraint("default_quantity > 0", name="positive_default_quantity"),
        UniqueConstraint("user_id", "normalized_name"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    default_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="🛒")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    department: Mapped[Department] = relationship()

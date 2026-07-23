from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.catalog import CatalogCategory, Product


class Recipe(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("base_yield_quantity > 0", name="positive_base_yield"),
        CheckConstraint("yield_step > 0", name="positive_yield_step"),
        Index(
            "ix_recipes_name_trgm",
            "normalized_name",
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        ),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="🍽️")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    yield_label: Mapped[str] = mapped_column(String(64), nullable=False)
    base_yield_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    yield_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    yield_step: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    category: Mapped[CatalogCategory] = relationship()


class RecipeVariant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recipe_variants"
    __table_args__ = (
        UniqueConstraint("recipe_id", "code"),
        UniqueConstraint("recipe_id", "sort_order"),
    )

    recipe_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    recipe: Mapped[Recipe] = relationship()


class RecipeIngredient(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        UniqueConstraint("variant_id", "product_id"),
        UniqueConstraint("variant_id", "sort_order"),
    )

    variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product: Mapped[Product] = relationship()


class RecipeAddition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recipe_additions"

    list_id: Mapped[UUID] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_variants.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("space_members.id", ondelete="RESTRICT"), nullable=False
    )
    requested_yield_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    yield_unit: Mapped[str] = mapped_column(String(16), nullable=False)


class RecipeAdditionItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recipe_addition_items"
    __table_args__ = (UniqueConstraint("addition_id", "product_id"),)

    addition_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_additions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shopping_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("shopping_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

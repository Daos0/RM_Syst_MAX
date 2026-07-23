"""catalog recipes

Revision ID: b7f6e23d9a11
Revises: e48ca3afc6c6
Create Date: 2026-07-20 20:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f6e23d9a11"
down_revision: Union[str, Sequence[str], None] = "e48ca3afc6c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_categories",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('product', 'dish', 'supply')", name=op.f("ck_catalog_categories_valid_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_catalog_categories_code")),
        sa.UniqueConstraint("kind", "sort_order", name=op.f("uq_catalog_categories_kind")),
    )
    op.create_index(op.f("ix_catalog_categories_kind"), "catalog_categories", ["kind"], unique=False)

    op.add_column("products", sa.Column("catalog_category_id", sa.Uuid(), nullable=True))
    op.add_column("products", sa.Column("catalog_kind", sa.String(length=24), server_default="product", nullable=False))
    op.add_column("products", sa.Column("icon", sa.String(length=16), server_default="🛒", nullable=False))
    op.add_column("products", sa.Column("description", sa.Text(), server_default="", nullable=False))
    op.add_column("products", sa.Column("catalog_sort_order", sa.Integer(), server_default="0", nullable=False))
    op.create_check_constraint("ck_products_valid_catalog_kind", "products", "catalog_kind IN ('product', 'supply')")
    op.create_foreign_key(
        op.f("fk_products_catalog_category_id_catalog_categories"),
        "products",
        "catalog_categories",
        ["catalog_category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_products_catalog_category_id"), "products", ["catalog_category_id"], unique=False)

    op.create_table(
        "recipes",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("yield_label", sa.String(length=64), nullable=False),
        sa.Column("base_yield_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("yield_unit", sa.String(length=16), nullable=False),
        sa.Column("yield_step", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("base_yield_quantity > 0", name=op.f("ck_recipes_positive_base_yield")),
        sa.CheckConstraint("yield_step > 0", name=op.f("ck_recipes_positive_yield_step")),
        sa.ForeignKeyConstraint(["category_id"], ["catalog_categories.id"], name=op.f("fk_recipes_category_id_catalog_categories"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipes")),
        sa.UniqueConstraint("code", name=op.f("uq_recipes_code")),
        sa.UniqueConstraint("normalized_name", name=op.f("uq_recipes_normalized_name")),
    )
    op.create_index(op.f("ix_recipes_category_id"), "recipes", ["category_id"], unique=False)
    op.execute("CREATE INDEX ix_recipes_name_trgm ON recipes USING gin (normalized_name gin_trgm_ops)")

    op.create_table(
        "recipe_variants",
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], name=op.f("fk_recipe_variants_recipe_id_recipes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_variants")),
        sa.UniqueConstraint("recipe_id", "code", name=op.f("uq_recipe_variants_recipe_id")),
        sa.UniqueConstraint("recipe_id", "sort_order", name=op.f("uq_recipe_variants_recipe_id_sort_order")),
    )
    op.create_index(op.f("ix_recipe_variants_recipe_id"), "recipe_variants", ["recipe_id"], unique=False)

    op.create_table(
        "recipe_ingredients",
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_recipe_ingredients_positive_quantity")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_recipe_ingredients_product_id_products"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_id"], ["recipe_variants.id"], name=op.f("fk_recipe_ingredients_variant_id_recipe_variants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_ingredients")),
        sa.UniqueConstraint("variant_id", "product_id", name=op.f("uq_recipe_ingredients_variant_id")),
        sa.UniqueConstraint("variant_id", "sort_order", name=op.f("uq_recipe_ingredients_variant_id_sort_order")),
    )
    op.create_index(op.f("ix_recipe_ingredients_product_id"), "recipe_ingredients", ["product_id"], unique=False)
    op.create_index(op.f("ix_recipe_ingredients_variant_id"), "recipe_ingredients", ["variant_id"], unique=False)

    op.create_table(
        "recipe_additions",
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_member_id", sa.Uuid(), nullable=False),
        sa.Column("requested_yield_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("yield_unit", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["space_members.id"], name=op.f("fk_recipe_additions_created_by_member_id_space_members"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"], name=op.f("fk_recipe_additions_list_id_shopping_lists"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], name=op.f("fk_recipe_additions_recipe_id_recipes"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_id"], ["recipe_variants.id"], name=op.f("fk_recipe_additions_variant_id_recipe_variants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_additions")),
    )
    op.create_index(op.f("ix_recipe_additions_list_id"), "recipe_additions", ["list_id"], unique=False)
    op.create_index(op.f("ix_recipe_additions_recipe_id"), "recipe_additions", ["recipe_id"], unique=False)

    op.create_table(
        "recipe_addition_items",
        sa.Column("addition_id", sa.Uuid(), nullable=False),
        sa.Column("shopping_item_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["addition_id"], ["recipe_additions.id"], name=op.f("fk_recipe_addition_items_addition_id_recipe_additions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_recipe_addition_items_product_id_products"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shopping_item_id"], ["shopping_items.id"], name=op.f("fk_recipe_addition_items_shopping_item_id_shopping_items"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_addition_items")),
        sa.UniqueConstraint("addition_id", "product_id", name=op.f("uq_recipe_addition_items_addition_id")),
    )
    op.create_index(op.f("ix_recipe_addition_items_addition_id"), "recipe_addition_items", ["addition_id"], unique=False)
    op.create_index(op.f("ix_recipe_addition_items_shopping_item_id"), "recipe_addition_items", ["shopping_item_id"], unique=False)


def downgrade() -> None:
    op.drop_table("recipe_addition_items")
    op.drop_table("recipe_additions")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipe_variants")
    op.drop_index("ix_recipes_name_trgm", table_name="recipes")
    op.drop_table("recipes")
    op.drop_index(op.f("ix_products_catalog_category_id"), table_name="products")
    op.drop_constraint(op.f("fk_products_catalog_category_id_catalog_categories"), "products", type_="foreignkey")
    op.drop_constraint("ck_products_valid_catalog_kind", "products", type_="check")
    op.drop_column("products", "catalog_sort_order")
    op.drop_column("products", "description")
    op.drop_column("products", "icon")
    op.drop_column("products", "catalog_kind")
    op.drop_column("products", "catalog_category_id")
    op.drop_table("catalog_categories")

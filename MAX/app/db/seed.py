from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import (
    ColorPalette,
    CatalogCategory,
    Department,
    ListTemplate,
    Product,
    ProductAlias,
    Recipe,
    RecipeIngredient,
    RecipeVariant,
    TemplateItem,
)
from app.db.seed_data import ALIASES, COLORS, DEPARTMENTS, TEMPLATES
from app.db.session import Database


CATALOG_SEED_DIR = Path(__file__).with_name("bootstrap_catalog")


def catalog_seed_data() -> dict:
    result = {"categories": [], "products": [], "recipes": []}
    for path in sorted(CATALOG_SEED_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("category"):
            result["categories"].append(payload["category"])
        result["products"].extend(payload.get("products", []))
        result["recipes"].extend(payload.get("recipes", []))
    return result


async def seed_reference_data(database: Database) -> None:
    catalog_data = catalog_seed_data()
    async with database.sessions.begin() as session:
        color_insert = insert(ColorPalette).values(COLORS)
        await session.execute(
            color_insert.on_conflict_do_update(
                index_elements=[ColorPalette.key],
                set_={
                    "name": color_insert.excluded.name,
                    "light_hex": color_insert.excluded.light_hex,
                    "dark_hex": color_insert.excluded.dark_hex,
                    "text_hex": color_insert.excluded.text_hex,
                    "sort_order": color_insert.excluded.sort_order,
                    "is_active": True,
                },
            )
        )

        department_rows = [
            {"id": item_id, "code": code, "name": name, "sort_order": item_id}
            for item_id, code, name in DEPARTMENTS
        ]
        department_insert = insert(Department).values(department_rows)
        await session.execute(
            department_insert.on_conflict_do_update(
                index_elements=[Department.code],
                set_={
                    "name": department_insert.excluded.name,
                    "sort_order": department_insert.excluded.sort_order,
                    "is_active": True,
                },
            )
        )

        department_map = dict(
            (await session.execute(select(Department.code, Department.id))).all()
        )
        category_insert = insert(CatalogCategory).values(catalog_data["categories"])
        await session.execute(
            category_insert.on_conflict_do_update(
                index_elements=[CatalogCategory.code],
                set_={
                    "kind": category_insert.excluded.kind,
                    "name": category_insert.excluded.name,
                    "icon": category_insert.excluded.icon,
                    "description": category_insert.excluded.description,
                    "sort_order": category_insert.excluded.sort_order,
                    "is_active": True,
                },
            )
        )
        category_map = dict(
            (await session.execute(select(CatalogCategory.code, CatalogCategory.id))).all()
        )

        product_rows = [
            {
                "normalized_name": item["normalized_name"],
                "display_name": item["name"],
                "department_id": department_map[item["department_code"]],
                "catalog_category_id": category_map.get(item["category_code"]),
                "default_quantity": Decimal(str(item["quantity"])),
                "default_unit": item["unit"],
                "catalog_kind": item["kind"],
                "icon": item["icon"],
                "description": item["description"],
                "catalog_sort_order": item["sort_order"],
            }
            for item in catalog_data["products"]
        ]
        product_insert = insert(Product).values(product_rows)
        await session.execute(
            product_insert.on_conflict_do_update(
                index_elements=[Product.normalized_name],
                set_={
                    "display_name": product_insert.excluded.display_name,
                    "department_id": product_insert.excluded.department_id,
                    "catalog_category_id": product_insert.excluded.catalog_category_id,
                    "default_quantity": product_insert.excluded.default_quantity,
                    "default_unit": product_insert.excluded.default_unit,
                    "catalog_kind": product_insert.excluded.catalog_kind,
                    "icon": product_insert.excluded.icon,
                    "description": product_insert.excluded.description,
                    "catalog_sort_order": product_insert.excluded.catalog_sort_order,
                    "is_active": True,
                },
            )
        )

        product_map = dict(
            (await session.execute(select(Product.normalized_name, Product.id))).all()
        )
        alias_rows = [
            {"product_id": product_map[product_name], "alias": alias, "normalized_alias": alias}
            for product_name, aliases in ALIASES.items()
            for alias in aliases
        ]
        if alias_rows:
            alias_insert = insert(ProductAlias).values(alias_rows)
            await session.execute(
                alias_insert.on_conflict_do_update(
                    index_elements=[ProductAlias.normalized_alias],
                    set_={
                        "product_id": alias_insert.excluded.product_id,
                        "alias": alias_insert.excluded.alias,
                    },
                )
            )

        template_rows = [
            {"code": code, "title": values[0], "space_kind": values[1]}
            for code, values in TEMPLATES.items()
        ]
        template_insert = insert(ListTemplate).values(template_rows)
        await session.execute(
            template_insert.on_conflict_do_update(
                index_elements=[ListTemplate.code],
                set_={
                    "title": template_insert.excluded.title,
                    "space_kind": template_insert.excluded.space_kind,
                    "is_active": True,
                },
            )
        )
        template_map = dict(
            (await session.execute(select(ListTemplate.code, ListTemplate.id))).all()
        )
        template_item_rows = []
        product_defaults = {
            row["normalized_name"]: (row["default_quantity"], row["default_unit"])
            for row in product_rows
        }
        for code, (_, _, product_names) in TEMPLATES.items():
            for sort_order, product_name in enumerate(product_names, start=1):
                quantity, unit = product_defaults[product_name]
                template_item_rows.append(
                    {
                        "template_id": template_map[code],
                        "product_id": product_map[product_name],
                        "quantity": quantity,
                        "unit": unit,
                        "sort_order": sort_order,
                    }
                )
        template_item_insert = insert(TemplateItem).values(template_item_rows)
        await session.execute(
            template_item_insert.on_conflict_do_update(
                index_elements=[TemplateItem.template_id, TemplateItem.product_id],
                set_={
                    "quantity": template_item_insert.excluded.quantity,
                    "unit": template_item_insert.excluded.unit,
                    "sort_order": template_item_insert.excluded.sort_order,
                },
            )
        )

        recipe_rows = [
            {
                "code": item["code"],
                "category_id": category_map[item["category_code"]],
                "normalized_name": item["normalized_name"],
                "display_name": item["name"],
                "icon": item["icon"],
                "description": item["description"],
                "yield_label": item["yield_label"],
                "base_yield_quantity": Decimal(str(item["yield_quantity"])),
                "yield_unit": item["yield_unit"],
                "yield_step": Decimal(str(item["yield_step"])),
                "sort_order": item["sort_order"],
            }
            for item in catalog_data["recipes"]
        ]
        recipe_insert = insert(Recipe).values(recipe_rows)
        await session.execute(
            recipe_insert.on_conflict_do_update(
                index_elements=[Recipe.code],
                set_={
                    "category_id": recipe_insert.excluded.category_id,
                    "normalized_name": recipe_insert.excluded.normalized_name,
                    "display_name": recipe_insert.excluded.display_name,
                    "icon": recipe_insert.excluded.icon,
                    "description": recipe_insert.excluded.description,
                    "yield_label": recipe_insert.excluded.yield_label,
                    "base_yield_quantity": recipe_insert.excluded.base_yield_quantity,
                    "yield_unit": recipe_insert.excluded.yield_unit,
                    "yield_step": recipe_insert.excluded.yield_step,
                    "sort_order": recipe_insert.excluded.sort_order,
                    "is_active": True,
                },
            )
        )
        recipe_map = dict((await session.execute(select(Recipe.code, Recipe.id))).all())

        variant_rows = [
            {
                "recipe_id": recipe_map[recipe["code"]],
                "code": variant["code"],
                "name": variant["name"],
                "sort_order": variant["sort_order"],
                "is_default": variant["sort_order"] == 1,
            }
            for recipe in catalog_data["recipes"]
            for variant in recipe["variants"]
        ]
        variant_insert = insert(RecipeVariant).values(variant_rows)
        await session.execute(
            variant_insert.on_conflict_do_update(
                index_elements=[RecipeVariant.recipe_id, RecipeVariant.code],
                set_={
                    "name": variant_insert.excluded.name,
                    "sort_order": variant_insert.excluded.sort_order,
                    "is_default": variant_insert.excluded.is_default,
                    "is_active": True,
                },
            )
        )
        variant_map = {
            (recipe_code, variant_code): variant_id
            for recipe_code, variant_code, variant_id in (
                await session.execute(
                    select(Recipe.code, RecipeVariant.code, RecipeVariant.id)
                    .join(Recipe, Recipe.id == RecipeVariant.recipe_id)
                )
            ).all()
        }
        ingredient_rows = [
            {
                "variant_id": variant_map[(recipe["code"], variant["code"])],
                "product_id": product_map[ingredient["product_normalized_name"]],
                "quantity": Decimal(str(ingredient["quantity"])),
                "unit": ingredient["unit"],
                "sort_order": ingredient["sort_order"],
                "is_optional": False,
            }
            for recipe in catalog_data["recipes"]
            for variant in recipe["variants"]
            for ingredient in variant["ingredients"]
        ]
        # Curated recipes are application-owned reference data. Rebuilding only
        # their ingredient rows makes corrections reach existing installations,
        # while personal products and shopping-list history stay untouched.
        await session.execute(
            delete(RecipeIngredient).where(RecipeIngredient.variant_id.in_(variant_map.values()))
        )
        await session.execute(insert(RecipeIngredient).values(ingredient_rows))


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for database seed")
    database = Database(database_url)
    try:
        await seed_reference_data(database)
    finally:
        await database.dispose()


if __name__ == "__main__":
    asyncio.run(main())

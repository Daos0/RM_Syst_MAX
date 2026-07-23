from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_optional_user_id, get_session
from app.api.normalization import normalize_name
from app.db.models import CatalogCategory, Department, Product, ProductAlias, Recipe, RecipeIngredient, RecipeVariant, UserCatalogItem


router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/catalog/suggestions")
async def suggestions(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    normalized = normalize_name(q)
    exact_alias = (
        select(ProductAlias.id)
        .where(
            ProductAlias.product_id == Product.id,
            ProductAlias.normalized_alias == normalized,
        )
        .exists()
    )
    rows = (
        await session.execute(
            select(Product)
            .where(
                Product.is_active.is_(True),
                or_(
                    Product.normalized_name.ilike(f"%{normalized}%"),
                    select(ProductAlias.id)
                    .where(
                        ProductAlias.product_id == Product.id,
                        ProductAlias.normalized_alias.ilike(f"%{normalized}%"),
                    )
                    .exists(),
                ),
            )
            .order_by(
                (Product.normalized_name == normalized).desc(),
                exact_alias.desc(),
                func.similarity(Product.normalized_name, normalized).desc(),
                Product.display_name,
            )
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(product.id),
            "name": product.display_name,
            "department_id": product.department_id,
            "quantity": str(product.default_quantity),
            "unit": product.default_unit,
        }
        for product in rows
    ]


def category_json(category: CatalogCategory) -> dict:
    return {
        "id": str(category.id),
        "code": category.code,
        "kind": category.kind,
        "name": category.name,
        "icon": category.icon,
        "description": category.description,
        "sort_order": category.sort_order,
    }


@router.get("/catalog")
async def full_catalog(response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    response.headers["Cache-Control"] = "private, max-age=300, stale-while-revalidate=86400"
    categories = (
        await session.execute(
            select(CatalogCategory)
            .where(CatalogCategory.is_active.is_(True))
            .order_by(CatalogCategory.kind, CatalogCategory.sort_order)
        )
    ).scalars().all()
    product_rows = (
        await session.execute(
            select(Product, Department, CatalogCategory)
            .join(Department, Department.id == Product.department_id)
            .outerjoin(CatalogCategory, CatalogCategory.id == Product.catalog_category_id)
            .where(Product.is_active.is_(True))
            .order_by(Product.catalog_kind, CatalogCategory.sort_order.nulls_last(), Product.catalog_sort_order, Product.display_name)
        )
    ).all()
    recipe_rows = (
        await session.execute(
            select(Recipe, CatalogCategory)
            .join(CatalogCategory, CatalogCategory.id == Recipe.category_id)
            .where(Recipe.is_active.is_(True))
            .order_by(CatalogCategory.sort_order, Recipe.sort_order)
        )
    ).all()
    variants = (
        await session.execute(
            select(RecipeVariant)
            .where(RecipeVariant.is_active.is_(True))
            .order_by(RecipeVariant.recipe_id, RecipeVariant.sort_order)
        )
    ).scalars().all()
    ingredient_rows = (
        await session.execute(
            select(RecipeIngredient, Product, Department)
            .join(Product, Product.id == RecipeIngredient.product_id)
            .join(Department, Department.id == Product.department_id)
            .order_by(RecipeIngredient.variant_id, RecipeIngredient.sort_order)
        )
    ).all()

    ingredients_by_variant: dict[UUID, list[dict]] = {}
    for ingredient, product, department in ingredient_rows:
        ingredients_by_variant.setdefault(ingredient.variant_id, []).append(
            {
                "product_id": str(product.id),
                "name": product.display_name,
                "quantity": str(ingredient.quantity),
                "unit": ingredient.unit,
                "department_id": department.id,
                "department": department.name,
                "optional": ingredient.is_optional,
                "sort_order": ingredient.sort_order,
            }
        )
    variants_by_recipe: dict[UUID, list[dict]] = {}
    for variant in variants:
        variants_by_recipe.setdefault(variant.recipe_id, []).append(
            {
                "id": str(variant.id),
                "code": variant.code,
                "name": variant.name,
                "default": variant.is_default,
                "sort_order": variant.sort_order,
                "ingredients": ingredients_by_variant.get(variant.id, []),
            }
        )

    return {
        "categories": [category_json(category) for category in categories],
        "products": [
            {
                "id": str(product.id),
                "name": product.display_name,
                "normalized_name": product.normalized_name,
                "kind": product.catalog_kind,
                "category_id": str(category.id) if category else None,
                "category_code": category.code if category else None,
                "icon": product.icon,
                "description": product.description,
                "quantity": str(product.default_quantity),
                "unit": product.default_unit,
                "department_id": department.id,
                "department": department.name,
                "sort_order": product.catalog_sort_order,
            }
            for product, department, category in product_rows
        ],
        "recipes": [
            {
                "id": str(recipe.id),
                "code": recipe.code,
                "name": recipe.display_name,
                "normalized_name": recipe.normalized_name,
                "category_id": str(category.id),
                "category_code": category.code,
                "icon": recipe.icon,
                "description": recipe.description,
                "yield": {
                    "label": recipe.yield_label,
                    "quantity": str(recipe.base_yield_quantity),
                    "unit": recipe.yield_unit,
                    "step": str(recipe.yield_step),
                },
                "sort_order": recipe.sort_order,
                "variants": variants_by_recipe.get(recipe.id, []),
            }
            for recipe, category in recipe_rows
        ],
    }


@router.get("/catalog/search")
async def unified_catalog_search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=24, ge=1, le=50),
    user_id: UUID | None = Depends(get_optional_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    normalized = normalize_name(q)
    products = (
        await session.execute(
            select(Product, Department, CatalogCategory)
            .join(Department, Department.id == Product.department_id)
            .outerjoin(CatalogCategory, CatalogCategory.id == Product.catalog_category_id)
            .where(Product.is_active.is_(True), Product.normalized_name.ilike(f"%{normalized}%"))
            .order_by(
                (Product.normalized_name == normalized).desc(),
                func.similarity(Product.normalized_name, normalized).desc(),
                Product.display_name,
            )
            .limit(limit)
        )
    ).all()
    recipes = (
        await session.execute(
            select(Recipe, CatalogCategory)
            .join(CatalogCategory, CatalogCategory.id == Recipe.category_id)
            .where(Recipe.is_active.is_(True), Recipe.normalized_name.ilike(f"%{normalized}%"))
            .order_by(
                (Recipe.normalized_name == normalized).desc(),
                func.similarity(Recipe.normalized_name, normalized).desc(),
                Recipe.display_name,
            )
            .limit(limit)
        )
    ).all()
    personal_rows = []
    if user_id:
        personal_rows = (
            await session.execute(
                select(UserCatalogItem, Department)
                .join(Department, Department.id == UserCatalogItem.department_id)
                .where(
                    UserCatalogItem.user_id == user_id,
                    UserCatalogItem.is_active.is_(True),
                    UserCatalogItem.normalized_name.ilike(f"%{normalized}%"),
                )
                .order_by(
                    (UserCatalogItem.normalized_name == normalized).desc(),
                    UserCatalogItem.display_name,
                )
                .limit(limit)
            )
        ).all()
    results = [
        {
            "id": str(product.id),
            "kind": product.catalog_kind,
            "name": product.display_name,
            "icon": product.icon,
            "category": category.name if category else department.name,
            "detail": product.description or f"{product.default_quantity:g} {product.default_unit}",
            "exact": product.normalized_name == normalized,
        }
        for product, department, category in products
    ] + [
        {
            "id": str(recipe.id),
            "kind": "dish",
            "name": recipe.display_name,
            "icon": recipe.icon,
            "category": category.name,
            "detail": f"{recipe.base_yield_quantity:g} {recipe.yield_unit}",
            "exact": recipe.normalized_name == normalized,
        }
        for recipe, category in recipes
    ] + [
        {
            "id": str(item.id),
            "kind": "product",
            "source": "personal",
            "name": item.display_name,
            "icon": item.icon,
            "category": department.name,
            "detail": f"{item.default_quantity:g} {item.default_unit}",
            "exact": item.normalized_name == normalized,
        }
        for item, department in personal_rows
    ]
    kind_rank = {"dish": 0, "product": 1, "supply": 2}
    results.sort(key=lambda item: (not item.pop("exact"), kind_rank[item["kind"]], item["name"]))
    return results[:limit]

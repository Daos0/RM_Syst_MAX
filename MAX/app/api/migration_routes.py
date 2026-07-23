from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_routes import cabinet_payload, ensure_user_spaces
from app.api.dependencies import get_current_user, get_session
from app.api.normalization import normalize_name
from app.api.routes import canonical_quantity, product_dedupe_key
from app.api.schemas import LocalMigrationRequest
from app.api.starter_lists import ensure_starter_lists, seed_template_items
from app.db.models import (
    Department,
    ListTemplate,
    Product,
    ProductAlias,
    ShoppingItem,
    ShoppingList,
    User,
    UserCatalogItem,
)

router = APIRouter(prefix="/api/v1/migrations", tags=["migration"])


async def resolve_product(session: AsyncSession, normalized: str) -> Product | None:
    return await session.scalar(
        select(Product)
        .outerjoin(ProductAlias, ProductAlias.product_id == Product.id)
        .where(
            Product.is_active.is_(True),
            or_(
                Product.normalized_name == normalized,
                ProductAlias.normalized_alias == normalized,
            ),
        )
        .limit(1)
    )


@router.post("/local-storage")
async def migrate_local_storage(
    payload: LocalMigrationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    completed = list(user.settings.get("completed_migrations", []))
    if payload.migration_id in completed:
        async with session.begin():
            spaces = await ensure_user_spaces(session, user)
            await ensure_starter_lists(session, user, spaces)
        return await cabinet_payload(session, user)

    async with session.begin():
        spaces = await ensure_user_spaces(session, user)
        spaces_by_kind = {space.kind: (space, member) for space, member in spaces}
        departments = (
            await session.execute(select(Department).where(Department.is_active.is_(True)))
        ).scalars().all()
        department_by_name = {row.name: row.id for row in departments}
        templates = (
            await session.execute(select(ListTemplate).where(ListTemplate.is_active.is_(True)))
        ).scalars().all()
        template_by_key = {(row.space_kind, row.title): row for row in templates}

        for legacy_list in payload.lists:
            space, member = spaces_by_kind[legacy_list.category]
            shopping_list = await session.scalar(
                select(ShoppingList).where(
                    ShoppingList.space_id == space.id,
                    ShoppingList.title == legacy_list.title.strip(),
                    ShoppingList.status != "archived",
                )
            )
            if shopping_list is None:
                template = template_by_key.get((legacy_list.category, legacy_list.title))
                shopping_list = ShoppingList(
                    space_id=space.id,
                    template_id=template.id if template else None,
                    created_by_member_id=member.id,
                    title=legacy_list.title.strip(),
                    category=legacy_list.category,
                )
                session.add(shopping_list)
                await session.flush()
                if template and not legacy_list.items:
                    await seed_template_items(session, shopping_list, member.id, template)

            for legacy_item in legacy_list.items:
                normalized = normalize_name(legacy_item.name)
                product = await resolve_product(session, normalized)
                department_id = department_by_name.get(
                    legacy_item.category or "",
                    product.department_id if product else 14,
                )
                quantity, unit, family = canonical_quantity(
                    legacy_item.quantity, legacy_item.unit
                )
                dedupe_key = (
                    product_dedupe_key(product.id, family)
                    if product
                    else f"custom:{normalized}:{family}"
                )
                item_insert = insert(ShoppingItem).values(
                    list_id=shopping_list.id,
                    product_id=product.id if product else None,
                    department_id=department_id,
                    created_by_member_id=member.id,
                    display_name=product.display_name if product else legacy_item.name.strip(),
                    dedupe_key=dedupe_key,
                    quantity=quantity,
                    unit=unit,
                    note=legacy_item.note,
                    status=legacy_item.status,
                    mark=legacy_item.mark,
                    purchased_by_member_id=member.id if legacy_item.status == "purchased" else None,
                )
                await session.execute(
                    item_insert.on_conflict_do_update(
                        index_elements=[ShoppingItem.list_id, ShoppingItem.dedupe_key],
                        index_where=ShoppingItem.deleted_at.is_(None),
                        set_={
                            "quantity": item_insert.excluded.quantity,
                            "unit": item_insert.excluded.unit,
                            "department_id": item_insert.excluded.department_id,
                            "note": item_insert.excluded.note,
                            "status": item_insert.excluded.status,
                            "mark": item_insert.excluded.mark,
                            "purchased_by_member_id": item_insert.excluded.purchased_by_member_id,
                            "version": ShoppingItem.version + 1,
                            "updated_at": func.now(),
                        },
                    )
                )

        for personal in payload.personal_catalog:
            normalized = normalize_name(personal.name)
            product = await resolve_product(session, normalized)
            if product:
                continue
            department_id = department_by_name.get(personal.category or "", 14)
            quantity, unit, _ = canonical_quantity(personal.quantity, personal.unit)
            personal_insert = insert(UserCatalogItem).values(
                user_id=user.id,
                normalized_name=normalized,
                display_name=personal.name.strip(),
                department_id=department_id,
                default_quantity=quantity,
                default_unit=unit,
                icon="🛒",
            )
            await session.execute(
                personal_insert.on_conflict_do_update(
                    index_elements=[UserCatalogItem.user_id, UserCatalogItem.normalized_name],
                    set_={
                        "display_name": personal_insert.excluded.display_name,
                        "department_id": personal_insert.excluded.department_id,
                        "default_quantity": personal_insert.excluded.default_quantity,
                        "default_unit": personal_insert.excluded.default_unit,
                        "is_active": True,
                        "updated_at": func.now(),
                    },
                )
            )

        await ensure_starter_lists(session, user, spaces)

        settings = dict(user.settings)
        settings["completed_migrations"] = [*completed, payload.migration_id]
        settings["legacy_product_usage"] = payload.product_usage
        settings["legacy_recipe_usage"] = payload.recipe_usage
        user.settings = settings

    return await cabinet_payload(session, user)

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_user_id
from app.api.list_removal_service import remove_list_for_member
from app.api.normalization import normalize_name
from app.api.schemas import (
    BootstrapRequest,
    ItemCreateRequest,
    ItemUpdateRequest,
    ListCreateRequest,
    ListUpdateRequest,
    RecipeAddRequest,
)
from app.api.shared_space_service import space_for_new_list
from app.db.models import (
    ColorPalette,
    Department,
    ListTemplate,
    OutboxEvent,
    Product,
    ProductAlias,
    ProductUserStat,
    Recipe,
    RecipeAddition,
    RecipeAdditionItem,
    RecipeIngredient,
    RecipeVariant,
    ShoppingEvent,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    TemplateItem,
    User,
    UserCatalogItem,
)

router = APIRouter(prefix="/api/v1", tags=["shopping"])


async def current_member(
    session: AsyncSession,
    user_id: UUID,
    *,
    space_id: UUID | None = None,
    list_id: UUID | None = None,
) -> SpaceMember:
    statement = select(SpaceMember)
    if list_id is not None:
        statement = statement.join(
            ShoppingList, ShoppingList.space_id == SpaceMember.space_id
        ).where(ShoppingList.id == list_id)
    elif space_id is not None:
        statement = statement.where(SpaceMember.space_id == space_id)
    member = await session.scalar(
        statement.where(
            SpaceMember.user_id == user_id, SpaceMember.left_at.is_(None)
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Нет доступа к этому пространству")
    return member


def add_event(
    session: AsyncSession,
    *,
    shopping_list: ShoppingList,
    member: SpaceMember,
    event_type: str,
    item_id: UUID | None = None,
    data: dict | None = None,
) -> None:
    payload = data or {}
    session.add(
        ShoppingEvent(
            list_id=shopping_list.id,
            item_id=item_id,
            actor_member_id=member.id,
            event_type=event_type,
            event_data=payload,
        )
    )
    session.add(
        OutboxEvent(
            aggregate_type="shopping_list",
            aggregate_id=shopping_list.id,
            event_type=event_type,
            payload={"list_id": str(shopping_list.id), "item_id": str(item_id) if item_id else None, **payload},
        )
    )


def item_json(item: ShoppingItem) -> dict:
    return {
        "id": str(item.id),
        "product_id": str(item.product_id) if item.product_id else None,
        "display_name": item.display_name,
        "quantity": str(item.quantity),
        "unit": item.unit,
        "department_id": item.department_id,
        "note": item.note,
        "mark": item.mark,
        "status": item.status,
        "assigned_member_id": str(item.assigned_member_id) if item.assigned_member_id else None,
        "purchased_by_member_id": str(item.purchased_by_member_id) if item.purchased_by_member_id else None,
        "version": item.version,
    }


def canonical_quantity(quantity: Decimal, unit: str) -> tuple[Decimal, str, str]:
    normalized_unit = unit.strip().casefold()
    if normalized_unit == "г":
        return quantity / Decimal("1000"), "кг", "mass"
    if normalized_unit == "кг":
        return quantity, "кг", "mass"
    if normalized_unit == "мл":
        return quantity / Decimal("1000"), "л", "volume"
    if normalized_unit == "л":
        return quantity, "л", "volume"
    return quantity, unit, f"unit:{normalized_unit}"


def product_dedupe_key(product_id: UUID, unit_family: str) -> str:
    return f"product:{product_id}:{unit_family}"


@router.post("/bootstrap")
async def bootstrap(
    payload: BootstrapRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Требуется вход")
        user.display_name = payload.display_name.strip()
        user.username = payload.username
        user.locale = payload.locale

        membership = await session.scalar(
            select(SpaceMember)
            .join(Space, Space.id == SpaceMember.space_id)
            .where(
                Space.owner_user_id == user.id,
                Space.kind == "personal",
                SpaceMember.user_id == user.id,
                SpaceMember.left_at.is_(None),
            )
            .limit(1)
        )
        if membership is None:
            color_id = await session.scalar(
                select(ColorPalette.id)
                .where(ColorPalette.is_active.is_(True))
                .order_by(ColorPalette.sort_order)
                .limit(1)
            )
            space = Space(kind="personal", title="Моё пространство", owner_user_id=user.id)
            session.add(space)
            await session.flush()
            membership = SpaceMember(
                space_id=space.id,
                user_id=user.id,
                role="owner",
                color_id=color_id,
            )
            session.add(membership)
            await session.flush()
        else:
            space = await session.get(Space, membership.space_id)
            assert space is not None

        color = await session.get(ColorPalette, membership.color_id) if membership.color_id else None
        return {
            "user": {"id": str(user.id), "max_user_id": user.max_user_id, "display_name": user.display_name},
            "space": {"id": str(space.id), "title": space.title, "kind": space.kind},
            "member": {
                "id": str(membership.id),
                "role": membership.role,
                "color": None if color is None else {"key": color.key, "name": color.name, "light_hex": color.light_hex, "dark_hex": color.dark_hex, "text_hex": color.text_hex},
            },
        }


@router.get("/reference")
async def reference_data(session: AsyncSession = Depends(get_session)) -> dict:
    departments = (
        await session.execute(
            select(Department).where(Department.is_active.is_(True)).order_by(Department.sort_order)
        )
    ).scalars().all()
    templates = (
        await session.execute(
            select(ListTemplate).where(ListTemplate.is_active.is_(True)).order_by(ListTemplate.space_kind, ListTemplate.title)
        )
    ).scalars().all()
    return {
        "departments": [{"id": row.id, "code": row.code, "name": row.name, "sort_order": row.sort_order} for row in departments],
        "templates": [{"id": str(row.id), "code": row.code, "title": row.title, "category": row.space_kind} for row in templates],
    }


@router.get("/spaces/{space_id}/lists")
async def list_index(
    space_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await current_member(session, user_id, space_id=space_id)
    rows = (
        await session.execute(
            select(ShoppingList)
            .where(ShoppingList.space_id == space_id, ShoppingList.status != "archived")
            .order_by(ShoppingList.updated_at.desc())
        )
    ).scalars().all()
    return [{"id": str(row.id), "title": row.title, "category": row.category, "status": row.status, "version": row.version} for row in rows]


@router.post("/spaces/{space_id}/lists", status_code=status.HTTP_201_CREATED)
async def create_list(
    space_id: UUID,
    payload: ListCreateRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, space_id=space_id)
        target_space, member = await space_for_new_list(
            session,
            requested_space_id=space_id,
            category=payload.category,
            title=payload.title.strip(),
            user_id=user_id,
            current_member=member,
        )
        space_id = target_space.id
        template = None
        if payload.template_code:
            template = await session.scalar(
                select(ListTemplate).where(
                    ListTemplate.code == payload.template_code,
                    ListTemplate.space_kind == payload.category,
                    ListTemplate.is_active.is_(True),
                )
            )
            if template is None:
                raise HTTPException(status_code=422, detail="Шаблон не найден для выбранной категории")

        shopping_list = ShoppingList(
            space_id=space_id,
            template_id=template.id if template else None,
            created_by_member_id=member.id,
            title=payload.title.strip(),
            category=payload.category,
        )
        session.add(shopping_list)
        await session.flush()

        if template:
            template_rows = (
                await session.execute(
                    select(TemplateItem, Product)
                    .join(Product, Product.id == TemplateItem.product_id)
                    .where(TemplateItem.template_id == template.id)
                    .order_by(TemplateItem.sort_order)
                )
            ).all()
            template_items = []
            for template_item, product in template_rows:
                quantity, unit, family = canonical_quantity(
                    Decimal(template_item.quantity), template_item.unit
                )
                template_items.append(
                    ShoppingItem(
                        list_id=shopping_list.id,
                        product_id=product.id,
                        department_id=product.department_id,
                        created_by_member_id=member.id,
                        display_name=product.display_name,
                        dedupe_key=product_dedupe_key(product.id, family),
                        quantity=quantity,
                        unit=unit,
                    )
                )
            session.add_all(template_items)
        add_event(session, shopping_list=shopping_list, member=member, event_type="list.created", data={"title": shopping_list.title, "category": shopping_list.category})
        return {
            "id": str(shopping_list.id),
            "title": shopping_list.title,
            "category": shopping_list.category,
            "template_code": payload.template_code,
            "space_id": str(target_space.id),
            "space_title": target_space.title,
            "member_id": str(member.id),
            "role": member.role,
        }


@router.patch("/lists/{list_id}")
async def update_list(
    list_id: UUID,
    payload: ListUpdateRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, list_id=list_id)
        if member.role != "owner":
            raise HTTPException(status_code=403, detail="Только владелец может переименовать список")
        shopping_list = await session.get(ShoppingList, list_id)
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")
        shopping_list.title = payload.title.strip()
        shopping_list.version += 1
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="list.updated",
            data={"title": shopping_list.title},
        )
        return {
            "id": str(shopping_list.id),
            "title": shopping_list.title,
            "category": shopping_list.category,
            "status": shopping_list.status,
            "version": shopping_list.version,
        }


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_list(
    list_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    async with session.begin():
        shopping_list = await session.scalar(
            select(ShoppingList).where(ShoppingList.id == list_id).with_for_update()
        )
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")
        member = await current_member(session, user_id, list_id=list_id)
        outcome, successor = await remove_list_for_member(session, shopping_list, member)
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="list.archived" if outcome == "archived" else "list.member_left",
            data={
                "successor_member_id": str(successor.id) if successor else None,
            },
        )


@router.get("/lists/{list_id}")
async def get_list(
    list_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    member = await current_member(session, user_id, list_id=list_id)
    shopping_list = await session.get(ShoppingList, list_id)
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="Список не найден")
    rows = (
        await session.execute(
            select(ShoppingItem, Department)
            .join(Department, Department.id == ShoppingItem.department_id)
            .where(ShoppingItem.list_id == list_id, ShoppingItem.deleted_at.is_(None))
            .order_by(Department.sort_order, ShoppingItem.created_at)
        )
    ).all()
    groups: dict[int, dict] = {}
    for item, department in rows:
        group = groups.setdefault(department.id, {"id": department.id, "name": department.name, "sort_order": department.sort_order, "items": []})
        group["items"].append(item_json(item))
    return {
        "id": str(shopping_list.id),
        "title": shopping_list.title,
        "category": shopping_list.category,
        "status": shopping_list.status,
        "version": shopping_list.version,
        "current_member_id": str(member.id),
        "departments": list(groups.values()),
    }


async def resolve_product(session: AsyncSession, normalized: str) -> Product | None:
    return await session.scalar(
        select(Product)
        .outerjoin(ProductAlias, ProductAlias.product_id == Product.id)
        .where(
            Product.is_active.is_(True),
            or_(Product.normalized_name == normalized, ProductAlias.normalized_alias == normalized),
        )
        .limit(1)
    )


@router.post("/lists/{list_id}/items", status_code=status.HTTP_201_CREATED)
async def add_item(
    list_id: UUID,
    payload: ItemCreateRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, list_id=list_id)
        shopping_list = await session.get(ShoppingList, list_id)
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")
        normalized = normalize_name(payload.name)
        product = await resolve_product(session, normalized)
        department_id = payload.department_id or (product.department_id if product else 14)
        if await session.get(Department, department_id) is None:
            raise HTTPException(status_code=422, detail="Отдел магазина не найден")
        display_name = product.display_name if product else payload.name.strip()
        quantity = payload.quantity or (Decimal(product.default_quantity) if product else Decimal("1"))
        unit = payload.unit or (product.default_unit if product else "шт.")
        quantity, unit, family = canonical_quantity(quantity, unit)
        dedupe_key = (
            product_dedupe_key(product.id, family)
            if product
            else f"custom:{normalized}:{family}"
        )

        item_insert = insert(ShoppingItem).values(
            list_id=list_id,
            product_id=product.id if product else None,
            department_id=department_id,
            created_by_member_id=member.id,
            display_name=display_name,
            dedupe_key=dedupe_key,
            quantity=quantity,
            unit=unit,
            note=payload.note,
        )
        item = await session.scalar(
            item_insert.on_conflict_do_update(
                index_elements=[ShoppingItem.list_id, ShoppingItem.dedupe_key],
                index_where=ShoppingItem.deleted_at.is_(None),
                set_={
                    "quantity": ShoppingItem.quantity + quantity,
                    "note": func.coalesce(item_insert.excluded.note, ShoppingItem.note),
                    "version": ShoppingItem.version + 1,
                    "updated_at": func.now(),
                },
            ).returning(ShoppingItem)
        )
        assert item is not None
        if product:
            stat_insert = insert(ProductUserStat).values(
                user_id=member.user_id,
                product_id=product.id,
                add_count=1,
                purchase_count=0,
                last_added_at=func.now(),
            )
            await session.execute(
                stat_insert.on_conflict_do_update(
                    index_elements=[ProductUserStat.user_id, ProductUserStat.product_id],
                    set_={
                        "add_count": ProductUserStat.add_count + 1,
                        "last_added_at": func.now(),
                    },
                )
            )
        else:
            personal_insert = insert(UserCatalogItem).values(
                user_id=member.user_id,
                normalized_name=normalized,
                display_name=display_name,
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
        shopping_list.version += 1
        add_event(session, shopping_list=shopping_list, member=member, event_type="item.added", item_id=item.id, data={"quantity": str(quantity)})
        return item_json(item)


@router.patch("/items/{item_id}")
async def update_item(
    item_id: UUID,
    payload: ItemUpdateRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        item, shopping_list, member = await get_item_context(session, item_id, user_id)
        quantity, unit, family = canonical_quantity(
            payload.quantity or Decimal(item.quantity),
            payload.unit or item.unit,
        )
        dedupe_key = (
            product_dedupe_key(item.product_id, family)
            if item.product_id
            else f"custom:{normalize_name(item.display_name)}:{family}"
        )
        target = await session.scalar(
            select(ShoppingItem).where(
                ShoppingItem.list_id == item.list_id,
                ShoppingItem.dedupe_key == dedupe_key,
                ShoppingItem.id != item.id,
                ShoppingItem.deleted_at.is_(None),
            )
        )
        if target is not None:
            target.quantity = Decimal(target.quantity) + quantity
            target.version += 1
            item.deleted_at = datetime.now(timezone.utc)
            item = target
        else:
            item.quantity = quantity
            item.unit = unit
            item.dedupe_key = dedupe_key

        if payload.department_id is not None:
            if await session.get(Department, payload.department_id) is None:
                raise HTTPException(status_code=422, detail="Отдел магазина не найден")
            item.department_id = payload.department_id
        if "note" in payload.model_fields_set:
            item.note = payload.note
        if payload.mark is not None:
            item.mark = payload.mark
        if payload.status is not None:
            previous_status = item.status
            item.status = payload.status
            if payload.status == "purchased":
                item.purchased_by_member_id = member.id
                item.purchased_at = datetime.now(timezone.utc)
                item.assigned_member_id = None
                if previous_status != "purchased" and item.product_id:
                    stat_insert = insert(ProductUserStat).values(
                        user_id=member.user_id,
                        product_id=item.product_id,
                        add_count=0,
                        purchase_count=1,
                        last_purchased_at=func.now(),
                    )
                    await session.execute(
                        stat_insert.on_conflict_do_update(
                            index_elements=[ProductUserStat.user_id, ProductUserStat.product_id],
                            set_={
                                "purchase_count": ProductUserStat.purchase_count + 1,
                                "last_purchased_at": func.now(),
                            },
                        )
                    )
            else:
                item.purchased_by_member_id = None
                item.purchased_at = None
                if payload.status in {"active", "unavailable"}:
                    item.assigned_member_id = None
        item.version += 1
        shopping_list.version += 1
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="item.updated",
            item_id=item.id,
            data={"fields": sorted(payload.model_fields_set)},
        )
        await session.flush()
        return item_json(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    async with session.begin():
        item, shopping_list, member = await get_item_context(session, item_id, user_id)
        item.deleted_at = datetime.now(timezone.utc)
        item.version += 1
        shopping_list.version += 1
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="item.deleted",
            item_id=item.id,
        )


@router.post("/lists/{list_id}/recipes/{recipe_id}", status_code=status.HTTP_201_CREATED)
async def add_recipe_to_list(
    list_id: UUID,
    recipe_id: UUID,
    payload: RecipeAddRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, list_id=list_id)
        shopping_list = await session.get(ShoppingList, list_id)
        recipe = await session.get(Recipe, recipe_id)
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")
        if recipe is None or not recipe.is_active:
            raise HTTPException(status_code=404, detail="Блюдо не найдено")
        if payload.variant_id:
            variant = await session.get(RecipeVariant, payload.variant_id)
            if variant is None or variant.recipe_id != recipe.id or not variant.is_active:
                raise HTTPException(status_code=422, detail="Вариант не относится к выбранному блюду")
        else:
            variant = await session.scalar(
                select(RecipeVariant)
                .where(RecipeVariant.recipe_id == recipe.id, RecipeVariant.is_active.is_(True))
                .order_by(RecipeVariant.is_default.desc(), RecipeVariant.sort_order)
                .limit(1)
            )
        if variant is None:
            raise HTTPException(status_code=422, detail="У блюда нет доступного варианта")

        ingredient_rows = (
            await session.execute(
                select(RecipeIngredient, Product)
                .join(Product, Product.id == RecipeIngredient.product_id)
                .where(RecipeIngredient.variant_id == variant.id)
                .order_by(RecipeIngredient.sort_order)
            )
        ).all()
        excluded = set(payload.excluded_product_ids)
        selected_rows = [(ingredient, product) for ingredient, product in ingredient_rows if product.id not in excluded]
        if not selected_rows:
            raise HTTPException(status_code=422, detail="Выберите хотя бы один ингредиент")

        scale = payload.yield_quantity / Decimal(recipe.base_yield_quantity)
        addition = RecipeAddition(
            list_id=list_id,
            recipe_id=recipe.id,
            variant_id=variant.id,
            created_by_member_id=member.id,
            requested_yield_quantity=payload.yield_quantity,
            yield_unit=recipe.yield_unit,
        )
        session.add(addition)
        await session.flush()

        added_items: list[dict] = []
        for ingredient, product in selected_rows:
            raw_quantity = (Decimal(ingredient.quantity) * scale).quantize(Decimal("0.001"))
            quantity, unit, family = canonical_quantity(raw_quantity, ingredient.unit)
            quantity = quantity.quantize(Decimal("0.001"))
            dedupe_key = product_dedupe_key(product.id, family)
            item_insert = insert(ShoppingItem).values(
                list_id=list_id,
                product_id=product.id,
                department_id=product.department_id,
                created_by_member_id=member.id,
                display_name=product.display_name,
                dedupe_key=dedupe_key,
                quantity=quantity,
                unit=unit,
                note=None,
            )
            item = await session.scalar(
                item_insert.on_conflict_do_update(
                    index_elements=[ShoppingItem.list_id, ShoppingItem.dedupe_key],
                    index_where=ShoppingItem.deleted_at.is_(None),
                    set_={
                        "quantity": ShoppingItem.quantity + quantity,
                        "version": ShoppingItem.version + 1,
                        "updated_at": func.now(),
                    },
                ).returning(ShoppingItem)
            )
            assert item is not None
            session.add(
                RecipeAdditionItem(
                    addition_id=addition.id,
                    shopping_item_id=item.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit=unit,
                )
            )
            stat_insert = insert(ProductUserStat).values(
                user_id=member.user_id,
                product_id=product.id,
                add_count=1,
                purchase_count=0,
                last_added_at=func.now(),
            )
            await session.execute(
                stat_insert.on_conflict_do_update(
                    index_elements=[ProductUserStat.user_id, ProductUserStat.product_id],
                    set_={
                        "add_count": ProductUserStat.add_count + 1,
                        "last_added_at": func.now(),
                    },
                )
            )
            added_items.append(item_json(item))

        shopping_list.version += 1
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="recipe.added",
            data={
                "recipe_id": str(recipe.id),
                "variant_id": str(variant.id),
                "addition_id": str(addition.id),
                "yield_quantity": str(payload.yield_quantity),
                "yield_unit": recipe.yield_unit,
                "ingredient_count": len(added_items),
            },
        )
        return {
            "addition_id": str(addition.id),
            "recipe": recipe.display_name,
            "variant": variant.name,
            "yield_quantity": str(payload.yield_quantity),
            "yield_unit": recipe.yield_unit,
            "items": added_items,
        }


async def get_item_context(
    session: AsyncSession, item_id: UUID, user_id: UUID
) -> tuple[ShoppingItem, ShoppingList, SpaceMember]:
    item = await session.get(ShoppingItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    shopping_list = await session.get(ShoppingList, item.list_id)
    assert shopping_list is not None
    member = await current_member(session, user_id, list_id=shopping_list.id)
    return item, shopping_list, member

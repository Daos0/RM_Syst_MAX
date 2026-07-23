from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import canonical_quantity, product_dedupe_key
from app.db.models import (
    ListTemplate,
    Product,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    TemplateItem,
    User,
)

STARTER_TEMPLATE_CODES = {
    "personal": ("personal_dinner", "personal_breakfast"),
    "family": ("family_dinner", "family_bbq"),
}
STARTER_SETTINGS_KEY = "starter_lists_v1"


async def seed_template_items(
    session: AsyncSession,
    shopping_list: ShoppingList,
    member_id,
    template: ListTemplate,
) -> None:
    rows = (
        await session.execute(
            select(TemplateItem, Product)
            .join(Product, Product.id == TemplateItem.product_id)
            .where(TemplateItem.template_id == template.id)
            .order_by(TemplateItem.sort_order)
        )
    ).all()
    for template_item, product in rows:
        quantity, unit, family = canonical_quantity(
            Decimal(template_item.quantity), template_item.unit
        )
        session.add(
            ShoppingItem(
                list_id=shopping_list.id,
                product_id=product.id,
                department_id=product.department_id,
                created_by_member_id=member_id,
                display_name=product.display_name,
                dedupe_key=product_dedupe_key(product.id, family),
                quantity=quantity,
                unit=unit,
            )
        )


async def ensure_starter_lists(
    session: AsyncSession,
    user: User,
    spaces: list[tuple[Space, SpaceMember]],
) -> None:
    if user.settings.get(STARTER_SETTINGS_KEY):
        return
    spaces_by_kind = {space.kind: (space, member) for space, member in spaces}
    active_counts = dict(
        (
            await session.execute(
                select(ShoppingList.space_id, func.count(ShoppingList.id))
                .where(
                    ShoppingList.space_id.in_([space.id for space, _ in spaces]),
                    ShoppingList.status != "archived",
                )
                .group_by(ShoppingList.space_id)
            )
        ).all()
    )
    codes = [code for values in STARTER_TEMPLATE_CODES.values() for code in values]
    templates = (
        await session.execute(
            select(ListTemplate).where(
                ListTemplate.code.in_(codes),
                ListTemplate.is_active.is_(True),
            )
        )
    ).scalars().all()
    templates_by_code = {template.code: template for template in templates}
    missing = set(codes) - templates_by_code.keys()
    if missing:
        raise RuntimeError(f"Не найдены стартовые шаблоны: {', '.join(sorted(missing))}")

    for kind, template_codes in STARTER_TEMPLATE_CODES.items():
        space, member = spaces_by_kind[kind]
        if active_counts.get(space.id, 0):
            continue
        for code in template_codes:
            template = templates_by_code[code]
            shopping_list = ShoppingList(
                space_id=space.id,
                template_id=template.id,
                created_by_member_id=member.id,
                title=template.title,
                category=kind,
            )
            session.add(shopping_list)
            await session.flush()
            await seed_template_items(session, shopping_list, member.id, template)

    settings = dict(user.settings)
    settings[STARTER_SETTINGS_KEY] = True
    user.settings = settings

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.routes import add_event
from app.db.models import (
    Department,
    ProductUserStat,
    ShoppingItem,
    ShoppingList,
    SpaceMember,
)
from app.db.session import Database
from app.platforms.identity import platform_user


BOT_ITEMS_PAGE_SIZE = 8


class BotShoppingError(RuntimeError):
    pass


def _quantity_text(value: Decimal, unit: str) -> str:
    number = format(value, "f").rstrip("0").rstrip(".") or "0"
    return f"{number.replace('.', ',')} {unit}"


async def _member_for_list(
    session,
    external_user_id: str | int,
    list_id: UUID,
    provider: str,
) -> SpaceMember | None:
    user = await platform_user(session, provider, external_user_id)
    if user is None:
        return None
    return await session.scalar(
        select(SpaceMember)
        .join(ShoppingList, ShoppingList.space_id == SpaceMember.space_id)
        .where(
            SpaceMember.user_id == user.id,
            SpaceMember.left_at.is_(None),
            ShoppingList.id == list_id,
            ShoppingList.status != "archived",
        )
    )


async def shopping_page_for_bot(
    database: Database,
    external_user_id: str | int,
    list_id: UUID,
    page: int = 0,
    *,
    provider: str = "max",
) -> dict:
    async with database.sessions() as session:
        member = await _member_for_list(
            session, external_user_id, list_id, provider
        )
        shopping_list = await session.get(ShoppingList, list_id)
        if member is None or shopping_list is None:
            raise BotShoppingError("Этот список вам недоступен")

        item_filter = (
            ShoppingItem.list_id == list_id,
            ShoppingItem.deleted_at.is_(None),
        )
        total = int(
            await session.scalar(
                select(func.count(ShoppingItem.id)).where(*item_filter)
            )
            or 0
        )
        purchased = int(
            await session.scalar(
                select(func.count(ShoppingItem.id)).where(
                    *item_filter, ShoppingItem.status == "purchased"
                )
            )
            or 0
        )
        total_pages = max(1, ceil(total / BOT_ITEMS_PAGE_SIZE))
        current_page = min(max(page, 0), total_pages - 1)
        rows = (
            await session.execute(
                select(ShoppingItem, Department)
                .join(Department, Department.id == ShoppingItem.department_id)
                .where(*item_filter)
                .order_by(Department.sort_order, ShoppingItem.created_at, ShoppingItem.id)
                .offset(current_page * BOT_ITEMS_PAGE_SIZE)
                .limit(BOT_ITEMS_PAGE_SIZE)
            )
        ).all()

    return {
        "id": str(shopping_list.id),
        "title": shopping_list.title,
        "total": total,
        "purchased": purchased,
        "page": current_page,
        "total_pages": total_pages,
        "items": [
            {
                "id": str(item.id),
                "name": item.display_name,
                "quantity": _quantity_text(Decimal(item.quantity), item.unit),
                "department": department.name,
                "status": item.status,
            }
            for item, department in rows
        ],
    }


async def set_item_status_from_bot(
    database: Database,
    external_user_id: str | int,
    item_id: UUID,
    desired_status: str,
    *,
    provider: str = "max",
) -> dict:
    if desired_status not in {"active", "purchased"}:
        raise BotShoppingError("Неизвестное действие")

    async with database.sessions.begin() as session:
        item = await session.scalar(
            select(ShoppingItem)
            .where(ShoppingItem.id == item_id, ShoppingItem.deleted_at.is_(None))
            .with_for_update()
        )
        if item is None:
            raise BotShoppingError("Товар уже удалён")
        shopping_list = await session.scalar(
            select(ShoppingList)
            .where(ShoppingList.id == item.list_id, ShoppingList.status != "archived")
            .with_for_update()
        )
        member = await _member_for_list(
            session, external_user_id, item.list_id, provider
        )
        if shopping_list is None or member is None:
            raise BotShoppingError("Этот список вам недоступен")

        changed = item.status != desired_status
        if changed:
            previous_status = item.status
            item.status = desired_status
            item.assigned_member_id = None
            if desired_status == "purchased":
                item.purchased_by_member_id = member.id
                item.purchased_at = datetime.now(timezone.utc)
                if previous_status != "purchased" and item.product_id:
                    stat = insert(ProductUserStat).values(
                        user_id=member.user_id,
                        product_id=item.product_id,
                        add_count=0,
                        purchase_count=1,
                        last_purchased_at=func.now(),
                    )
                    await session.execute(
                        stat.on_conflict_do_update(
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
            item.version += 1
            shopping_list.version += 1
            add_event(
                session,
                shopping_list=shopping_list,
                member=member,
                event_type="item.updated",
                item_id=item.id,
                data={"fields": ["status"], "source": "bot"},
            )

        return {
            "list_id": str(shopping_list.id),
            "name": item.display_name,
            "status": item.status,
            "changed": changed,
        }

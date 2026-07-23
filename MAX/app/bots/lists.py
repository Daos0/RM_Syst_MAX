from __future__ import annotations

from math import ceil

from sqlalchemy import case, func, select

from app.db.models import ShoppingItem, ShoppingList, SpaceMember
from app.db.session import Database
from app.platforms.identity import platform_user


async def lists_for_bot(
    database: Database,
    external_user_id: str | int,
    limit: int = 6,
    *,
    provider: str = "max",
) -> list[dict]:
    page = await list_page_for_bot(
        database,
        external_user_id,
        page_size=limit,
        provider=provider,
    )
    return page["lists"]


async def list_page_for_bot(
    database: Database,
    external_user_id: str | int,
    *,
    page: int = 0,
    page_size: int = 6,
    provider: str = "max",
) -> dict:
    priority = case(
        (ShoppingList.category == "shared", 0),
        (ShoppingList.category == "family", 1),
        else_=2,
    )
    async with database.sessions() as session:
        user = await platform_user(session, provider, external_user_id)
        if user is None:
            return {"page": 0, "total_pages": 1, "total": 0, "lists": []}
        filters = (
            SpaceMember.user_id == user.id,
            SpaceMember.left_at.is_(None),
            ShoppingList.status != "archived",
        )
        total = int(
            await session.scalar(
                select(func.count(ShoppingList.id))
                .join(SpaceMember, SpaceMember.space_id == ShoppingList.space_id)
                .where(*filters)
            )
            or 0
        )
        total_pages = max(1, ceil(total / page_size))
        current_page = min(max(page, 0), total_pages - 1)
        rows = (
            await session.execute(
                select(
                    ShoppingList,
                    func.count(ShoppingItem.id),
                    func.count(ShoppingItem.id).filter(ShoppingItem.status == "purchased"),
                )
                .join(SpaceMember, SpaceMember.space_id == ShoppingList.space_id)
                .outerjoin(
                    ShoppingItem,
                    (ShoppingItem.list_id == ShoppingList.id)
                    & ShoppingItem.deleted_at.is_(None),
                )
                .where(*filters)
                .group_by(ShoppingList.id)
                .order_by(priority, ShoppingList.updated_at.desc())
                .offset(current_page * page_size)
                .limit(page_size)
            )
        ).all()
    return {
        "page": current_page,
        "total_pages": total_pages,
        "total": total,
        "lists": [
            {
                "id": str(shopping_list.id),
                "title": shopping_list.title,
                "category": shopping_list.category,
                "item_count": int(item_count or 0),
                "purchased_count": int(purchased_count or 0),
            }
            for shopping_list, item_count, purchased_count in rows
        ],
    }

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_user_id
from app.api.routes import add_event, current_member
from app.api.schemas import ListItemsStatusRequest
from app.db.models import ProductUserStat, ShoppingItem, ShoppingList

router = APIRouter(prefix="/api/v1", tags=["list-actions"])


@router.patch("/lists/{list_id}/items/status")
async def set_all_items_status(
    list_id: UUID,
    payload: ListItemsStatusRequest,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, list_id=list_id)
        shopping_list = await session.get(ShoppingList, list_id)
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")

        items = (
            await session.scalars(
                select(ShoppingItem).where(
                    ShoppingItem.list_id == list_id,
                    ShoppingItem.deleted_at.is_(None),
                )
            )
        ).all()
        now = datetime.now(timezone.utc)
        purchase_counts: Counter[UUID] = Counter()
        changed = 0

        for item in items:
            if item.status == payload.status:
                continue
            if payload.status == "purchased" and item.product_id:
                purchase_counts[item.product_id] += 1
            item.status = payload.status
            item.assigned_member_id = None
            item.purchased_by_member_id = member.id if payload.status == "purchased" else None
            item.purchased_at = now if payload.status == "purchased" else None
            item.version += 1
            changed += 1

        for product_id, count in purchase_counts.items():
            stat_insert = insert(ProductUserStat).values(
                user_id=member.user_id,
                product_id=product_id,
                add_count=0,
                purchase_count=count,
                last_purchased_at=now,
            )
            await session.execute(
                stat_insert.on_conflict_do_update(
                    index_elements=[ProductUserStat.user_id, ProductUserStat.product_id],
                    set_={
                        "purchase_count": ProductUserStat.purchase_count + count,
                        "last_purchased_at": func.now(),
                    },
                )
            )

        if changed:
            shopping_list.version += 1
            add_event(
                session,
                shopping_list=shopping_list,
                member=member,
                event_type="list.items_status_changed",
                data={"status": payload.status, "count": changed},
            )

        return {
            "status": payload.status,
            "updated_items": changed,
            "list_version": shopping_list.version,
        }

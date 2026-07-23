from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_user_id
from app.api.routes import add_event, current_member, get_item_context, item_json
from app.db.models import ProductUserStat, SectionAssignment, ShoppingItem, ShoppingList

router = APIRouter(prefix="/api/v1", tags=["assignments"])


@router.post("/items/{item_id}/claim")
async def claim_item(
    item_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        item, shopping_list, member = await get_item_context(session, item_id, user_id)
        claimed = await session.scalar(
            update(ShoppingItem)
            .where(
                ShoppingItem.id == item_id,
                ShoppingItem.assigned_member_id.is_(None),
                ShoppingItem.status.in_(["active", "assigned"]),
            )
            .values(
                assigned_member_id=member.id,
                status="assigned",
                version=ShoppingItem.version + 1,
                updated_at=func.now(),
            )
            .returning(ShoppingItem)
        )
        if claimed is None:
            await session.refresh(item)
            if item.assigned_member_id == member.id:
                return item_json(item)
            raise HTTPException(status_code=409, detail="Товар уже закреплён за другим участником")
        shopping_list.version += 1
        add_event(session, shopping_list=shopping_list, member=member, event_type="item.claimed", item_id=item_id)
        return item_json(claimed)


@router.delete("/items/{item_id}/claim")
async def release_item(
    item_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        item, shopping_list, member = await get_item_context(session, item_id, user_id)
        if item.assigned_member_id not in (None, member.id) and member.role != "owner":
            raise HTTPException(status_code=403, detail="Освободить товар может ответственный или владелец")
        item.assigned_member_id = None
        if item.status == "assigned":
            item.status = "active"
        item.version += 1
        shopping_list.version += 1
        add_event(session, shopping_list=shopping_list, member=member, event_type="item.released", item_id=item_id)
        await session.flush()
        return item_json(item)


@router.post("/items/{item_id}/purchase")
async def purchase_item(
    item_id: UUID,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        item, shopping_list, member = await get_item_context(session, item_id, user_id)
        item.status = "purchased"
        item.purchased_by_member_id = member.id
        item.purchased_at = func.now()
        item.version += 1
        shopping_list.version += 1
        if item.product_id:
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
        add_event(session, shopping_list=shopping_list, member=member, event_type="item.purchased", item_id=item_id)
        await session.flush()
        return item_json(item)


@router.post("/lists/{list_id}/departments/{department_id}/claim")
async def claim_department(
    list_id: UUID,
    department_id: int,
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async with session.begin():
        member = await current_member(session, user_id, list_id=list_id)
        shopping_list = await session.get(ShoppingList, list_id)
        if shopping_list is None:
            raise HTTPException(status_code=404, detail="Список не найден")
        assignment_insert = insert(SectionAssignment).values(
            list_id=list_id, department_id=department_id, member_id=member.id
        )
        assignment = await session.scalar(
            assignment_insert.on_conflict_do_nothing(
                index_elements=[SectionAssignment.list_id, SectionAssignment.department_id]
            ).returning(SectionAssignment)
        )
        if assignment is None:
            existing = await session.scalar(
                select(SectionAssignment).where(
                    SectionAssignment.list_id == list_id,
                    SectionAssignment.department_id == department_id,
                )
            )
            if existing is None or existing.member_id != member.id:
                raise HTTPException(status_code=409, detail="Этот отдел уже взял другой участник")
            assignment = existing
        result = await session.execute(
            update(ShoppingItem)
            .where(
                ShoppingItem.list_id == list_id,
                ShoppingItem.department_id == department_id,
                ShoppingItem.deleted_at.is_(None),
                ShoppingItem.assigned_member_id.is_(None),
                ShoppingItem.status == "active",
            )
            .values(
                assigned_member_id=member.id,
                status="assigned",
                version=ShoppingItem.version + 1,
                updated_at=func.now(),
            )
        )
        shopping_list.version += 1
        add_event(
            session,
            shopping_list=shopping_list,
            member=member,
            event_type="department.claimed",
            data={"department_id": department_id},
        )
        return {
            "assignment_id": str(assignment.id),
            "member_id": str(member.id),
            "claimed_items": result.rowcount,
        }

import asyncio
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.bots.shopping import (
    BotShoppingError,
    set_item_status_from_bot,
    shopping_page_for_bot,
)
from app.db.models import (
    Department,
    ShoppingItem,
    ShoppingList,
    Space,
    SpaceMember,
    User,
)
from app.db.session import Database


DATABASE_URL = os.environ["DATABASE_URL"]


def test_bot_item_status_is_authorized_and_idempotent() -> None:
    max_user_id = int(uuid4().hex[:14], 16)

    async def scenario() -> None:
        database = Database(DATABASE_URL)
        try:
            async with database.sessions.begin() as session:
                user = User(
                    max_user_id=str(max_user_id),
                    display_name="Покупатель",
                    locale="ru",
                )
                session.add(user)
                await session.flush()
                space = Space(
                    kind="personal",
                    title="Личное",
                    owner_user_id=user.id,
                )
                session.add(space)
                await session.flush()
                member = SpaceMember(
                    space_id=space.id,
                    user_id=user.id,
                    role="owner",
                )
                session.add(member)
                await session.flush()
                shopping_list = ShoppingList(
                    space_id=space.id,
                    created_by_member_id=member.id,
                    title="Проверка бота",
                    category="personal",
                )
                session.add(shopping_list)
                await session.flush()
                department = await session.get(Department, 14)
                assert department is not None
                item = ShoppingItem(
                    list_id=shopping_list.id,
                    department_id=department.id,
                    created_by_member_id=member.id,
                    display_name="Тестовый товар",
                    dedupe_key=f"bot-test:{uuid4().hex}",
                    quantity=Decimal("2"),
                    unit="шт.",
                    status="active",
                )
                session.add(item)
                await session.flush()
                list_id = shopping_list.id
                item_id = item.id
                initial_version = shopping_list.version

            initial = await shopping_page_for_bot(database, max_user_id, list_id)
            assert initial["purchased"] == 0
            assert initial["items"][0]["quantity"] == "2 шт."

            purchased = await set_item_status_from_bot(
                database, max_user_id, item_id, "purchased"
            )
            assert purchased["changed"] is True
            repeated = await set_item_status_from_bot(
                database, max_user_id, item_id, "purchased"
            )
            assert repeated["changed"] is False

            updated = await shopping_page_for_bot(database, max_user_id, list_id)
            assert updated["purchased"] == 1
            assert updated["items"][0]["status"] == "purchased"

            with pytest.raises(BotShoppingError, match="недоступен"):
                await shopping_page_for_bot(database, max_user_id + 1, list_id)

            restored = await set_item_status_from_bot(
                database, max_user_id, item_id, "active"
            )
            assert restored["status"] == "active"
            async with database.sessions() as session:
                version = await session.scalar(
                    select(ShoppingList.version).where(ShoppingList.id == list_id)
                )
                event_count = await session.scalar(
                    select(func.count()).select_from(ShoppingItem).where(
                        ShoppingItem.id == item_id,
                        ShoppingItem.status == "active",
                    )
                )
            assert version == initial_version + 2
            assert event_count == 1
        finally:
            await database.dispose()

    asyncio.run(scenario())

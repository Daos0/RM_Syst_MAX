import asyncio
import hashlib
import hmac
import json
import os
import time
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.realtime_routes import visible_list_version
from app.bots.lists import lists_for_bot
from app.db.models import CatalogCategory, ColorPalette, Department, Product, Recipe, RecipeIngredient, SpaceMember, User
from app.db.session import Database
from app.main import create_app


DATABASE_URL = os.environ["DATABASE_URL"]


def signed_init_data(max_user_id: int, name: str, token: str = "test-token") -> str:
    params = {
        "auth_date": str(int(time.time())),
        "query_id": uuid4().hex,
        "user": json.dumps(
            {
                "id": max_user_id,
                "first_name": name,
                "last_name": "",
                "username": None,
                "language_code": "ru",
                "photo_url": None,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    launch_params = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, launch_params.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())


def authenticate(client: TestClient, max_user_id: int, name: str) -> tuple[dict, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/max",
        json={"init_data": signed_init_data(max_user_id, name)},
    )
    assert response.status_code == 200, response.text
    token = response.cookies.get("max_session")
    assert token
    return response.json(), {"Cookie": f"max_session={token}"}


async def add_member_to_space(max_user_id: int, space_id: str) -> None:
    database = Database(DATABASE_URL)
    try:
        async with database.sessions.begin() as session:
            user = await session.scalar(select(User).where(User.max_user_id == str(max_user_id)))
            assert user is not None
            session.add(
                SpaceMember(
                    space_id=space_id,
                    user_id=user.id,
                    role="editor",
                    color_id=2,
                )
            )
    finally:
        await database.dispose()


async def bot_list_state(max_user_id: int, list_id: str) -> tuple[list[dict], int | None]:
    database = Database(DATABASE_URL)
    try:
        lists = await lists_for_bot(database, max_user_id)
        async with database.sessions() as session:
            user = await session.scalar(select(User).where(User.max_user_id == str(max_user_id)))
            assert user is not None
            version = await visible_list_version(session, user.id, UUID(list_id))
        return lists, version
    finally:
        await database.dispose()


def test_seed_and_shopping_flow() -> None:
    suffix = uuid4().hex
    first_id = int(suffix[:14], 16)
    second_id = int(suffix[14:28], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["database_ready"] is True

        owner, owner_headers = authenticate(client, first_id, "Владелец")
        _, second_headers = authenticate(client, second_id, "Участник")
        space_id = next(space["id"] for space in owner["spaces"] if space["kind"] == "personal")
        asyncio.run(add_member_to_space(second_id, space_id))

        owner_session = client.get("/api/v1/auth/session", headers=owner_headers)
        assert owner_session.status_code == 200
        assert owner_session.json()["user"]["max_user_id"] == str(first_id)
        bearer_session = client.get(
            "/api/v1/auth/session",
            headers={"Authorization": f"Bearer {owner['session_token']}"},
        )
        assert bearer_session.status_code == 200
        assert bearer_session.json()["user"]["max_user_id"] == str(first_id)
        valid_for_forgery = signed_init_data(first_id, "Подмена")
        forged = valid_for_forgery[:-1] + ("0" if valid_for_forgery[-1] != "0" else "1")
        assert client.post("/api/v1/auth/max", json={"init_data": forged}).status_code == 401

        legacy_name = f"Личный продукт {suffix}"
        migration_payload = {
            "migration_id": "test_local_v1",
            "lists": [
                {
                    "title": "Перенесённый список",
                    "category": "personal",
                    "items": [
                        {
                            "name": legacy_name,
                            "quantity": "3",
                            "unit": "шт.",
                            "category": "Другое",
                            "status": "active",
                            "mark": "blue",
                        }
                    ],
                }
            ],
            "personal_catalog": [
                {"name": legacy_name, "quantity": "3", "unit": "шт.", "category": "Другое"}
            ],
        }
        migrated = client.post(
            "/api/v1/migrations/local-storage",
            headers=owner_headers,
            json=migration_payload,
        )
        assert migrated.status_code == 200, migrated.text
        migrated_again = client.post(
            "/api/v1/migrations/local-storage",
            headers=owner_headers,
            json=migration_payload,
        )
        assert migrated_again.status_code == 200
        migrated_lists = [
            item
            for space in migrated_again.json()["spaces"]
            for item in space["lists"]
            if item["title"] == "Перенесённый список"
        ]
        assert len(migrated_lists) == 1
        migrated_detail = client.get(
            f"/api/v1/lists/{migrated_lists[0]['id']}", headers=owner_headers
        )
        migrated_items = [
            item
            for department in migrated_detail.json()["departments"]
            for item in department["items"]
        ]
        assert migrated_items[0]["mark"] == "blue"

        reference = client.get("/api/v1/reference")
        assert reference.status_code == 200
        assert len(reference.json()["departments"]) == 14
        assert len(reference.json()["templates"]) == 10

        suggestions = client.get("/api/v1/catalog/suggestions?q=томат")
        assert suggestions.status_code == 200
        assert suggestions.json()[0]["name"] == "Помидоры"

        catalog = client.get("/api/v1/catalog")
        assert catalog.status_code == 200
        assert len(catalog.json()["categories"]) == 22
        assert len(catalog.json()["products"]) == 180
        assert len(catalog.json()["recipes"]) == 96
        mixed_search = client.get("/api/v1/catalog/search?q=кур")
        assert mixed_search.status_code == 200
        assert {item["kind"] for item in mixed_search.json()} >= {"product", "dish"}

        created = client.post(
            f"/api/v1/spaces/{space_id}/lists",
            headers=owner_headers,
            json={
                "title": "Тестовая неделя",
                "category": "personal",
                "template_code": "personal_week",
            },
        )
        assert created.status_code == 201, created.text
        list_id = created.json()["id"]

        personal_name = f"Авторский продукт {suffix}"
        personal_add = client.post(
            f"/api/v1/lists/{list_id}/items",
            headers=owner_headers,
            json={"name": personal_name, "quantity": "2", "unit": "шт.", "department_id": 14},
        )
        assert personal_add.status_code == 201, personal_add.text
        personal_search = client.get(
            "/api/v1/catalog/search",
            headers=owner_headers,
            params={"q": personal_name},
        )
        assert personal_search.status_code == 200
        assert personal_search.json()[0]["name"] == personal_name
        assert personal_search.json()[0]["source"] == "personal"

        first_add = client.post(
            f"/api/v1/lists/{list_id}/items",
            headers=owner_headers,
            json={"name": "Молоко", "quantity": "1", "unit": "л"},
        )
        assert first_add.status_code == 201, first_add.text
        bot_lists_before, version_before = asyncio.run(bot_list_state(first_id, list_id))
        assert any(item["id"] == list_id for item in bot_lists_before)
        assert version_before is not None
        second_add = client.post(
            f"/api/v1/lists/{list_id}/items",
            headers=owner_headers,
            json={"name": "молоко", "quantity": "1", "unit": "л"},
        )
        assert second_add.status_code == 201, second_add.text
        _, version_after = asyncio.run(bot_list_state(first_id, list_id))
        assert version_after is not None and version_after > version_before
        # В шаблоне уже было 2 л: повторные добавления увеличивают количество,
        # а не создают дублирующие строки.
        assert second_add.json()["quantity"] == "4.000"

        item_id = second_add.json()["id"]
        claimed = client.post(
            f"/api/v1/items/{item_id}/claim",
            headers=owner_headers,
        )
        assert claimed.status_code == 200
        conflict = client.post(
            f"/api/v1/items/{item_id}/claim",
            headers=second_headers,
        )
        assert conflict.status_code == 409

        shopping_list = client.get(
            f"/api/v1/lists/{list_id}",
            headers=owner_headers,
        )
        assert shopping_list.status_code == 200
        milk_rows = [
            item
            for department in shopping_list.json()["departments"]
            for item in department["items"]
            if item["display_name"] == "Молоко"
        ]
        assert len(milk_rows) == 1

        recipe_list = client.post(
            f"/api/v1/spaces/{space_id}/lists",
            headers=owner_headers,
            json={"title": "Борщ из БД", "category": "personal"},
        )
        assert recipe_list.status_code == 201
        borscht = next(item for item in catalog.json()["recipes"] if item["name"] == "Борщ")
        recipe_add = client.post(
            f"/api/v1/lists/{recipe_list.json()['id']}/recipes/{borscht['id']}",
            headers=owner_headers,
            json={"variant_id": borscht["variants"][0]["id"], "yield_quantity": "4"},
        )
        assert recipe_add.status_code == 201, recipe_add.text
        assert recipe_add.json()["recipe"] == "Борщ"
        assert len(recipe_add.json()["items"]) == 8

        merge_list = client.post(
            f"/api/v1/spaces/{space_id}/lists",
            headers=owner_headers,
            json={"title": "Объединение ингредиентов", "category": "personal"},
        )
        assert merge_list.status_code == 201
        merge_list_id = merge_list.json()["id"]
        grilled = next(
            item for item in catalog.json()["recipes"] if item["name"] == "Овощи на гриле"
        )
        grilled_add = client.post(
            f"/api/v1/lists/{merge_list_id}/recipes/{grilled['id']}",
            headers=owner_headers,
            json={"variant_id": grilled["variants"][0]["id"], "yield_quantity": "4"},
        )
        assert grilled_add.status_code == 201, grilled_add.text

        tomato_add = client.post(
            f"/api/v1/lists/{merge_list_id}/items",
            headers=owner_headers,
            json={"name": "Помидоры", "quantity": "0.5", "unit": "кг"},
        )
        assert tomato_add.status_code == 201, tomato_add.text
        assert tomato_add.json()["quantity"] == "1.000"

        merged_list = client.get(
            f"/api/v1/lists/{merge_list_id}",
            headers=owner_headers,
        )
        tomato_rows = [
            item
            for department in merged_list.json()["departments"]
            for item in department["items"]
            if item["display_name"] == "Помидоры"
        ]
        assert len(tomato_rows) == 1
        assert tomato_rows[0]["quantity"] == "1.000"

        marked_all = client.patch(
            f"/api/v1/lists/{merge_list_id}/items/status",
            headers=owner_headers,
            json={"status": "purchased"},
        )
        assert marked_all.status_code == 200, marked_all.text
        assert marked_all.json()["updated_items"] > 0
        purchased_list = client.get(
            f"/api/v1/lists/{merge_list_id}", headers=owner_headers
        ).json()
        assert {
            item["status"]
            for department in purchased_list["departments"]
            for item in department["items"]
        } == {"purchased"}

        restored_all = client.patch(
            f"/api/v1/lists/{merge_list_id}/items/status",
            headers=owner_headers,
            json={"status": "active"},
        )
        assert restored_all.status_code == 200, restored_all.text
        restored_list = client.get(
            f"/api/v1/lists/{merge_list_id}", headers=owner_headers
        ).json()
        assert {
            item["status"]
            for department in restored_list["departments"]
            for item in department["items"]
        } == {"active"}

        invalid_bulk_status = client.patch(
            f"/api/v1/lists/{merge_list_id}/items/status",
            headers=owner_headers,
            json={"status": "unavailable"},
        )
        assert invalid_bulk_status.status_code == 422


def test_reference_seed_counts() -> None:
    async def count_rows() -> tuple[int, int, int, int, int, int]:
        database = Database(DATABASE_URL)
        try:
            async with database.sessions() as session:
                colors = await session.scalar(select(func.count()).select_from(ColorPalette))
                departments = await session.scalar(select(func.count()).select_from(Department))
                products = await session.scalar(select(func.count()).select_from(Product))
                categories = await session.scalar(select(func.count()).select_from(CatalogCategory))
                recipes = await session.scalar(select(func.count()).select_from(Recipe))
                ingredients = await session.scalar(select(func.count()).select_from(RecipeIngredient))
                return (
                    int(colors or 0),
                    int(departments or 0),
                    int(products or 0),
                    int(categories or 0),
                    int(recipes or 0),
                    int(ingredients or 0),
                )
        finally:
            await database.dispose()

    assert asyncio.run(count_rows()) == (12, 14, 180, 22, 96, 491)


def test_new_user_gets_compact_starter_lists_once() -> None:
    max_user_id = int(uuid4().hex[:14], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        account, headers = authenticate(client, max_user_id, "Новый пользователь")
        assert all(not space["lists"] for space in account["spaces"])

        migration = client.post(
            "/api/v1/migrations/local-storage",
            headers=headers,
            json={"migration_id": "local_storage_v1", "lists": [], "personal_catalog": []},
        )
        assert migration.status_code == 200, migration.text
        spaces = {space["kind"]: space for space in migration.json()["spaces"]}
        assert {item["title"] for item in spaces["personal"]["lists"]} == {
            "Приготовить ужин",
            "Завтрак",
        }
        assert {item["title"] for item in spaces["family"]["lists"]} == {
            "Семейный ужин",
            "Шашлыки",
        }
        assert spaces["shared"]["lists"] == []
        assert sorted(item["item_count"] for item in spaces["personal"]["lists"]) == [4, 4]
        assert sorted(item["item_count"] for item in spaces["family"]["lists"]) == [5, 6]

        repeated = client.post(
            "/api/v1/migrations/local-storage",
            headers=headers,
            json={"migration_id": "local_storage_v1", "lists": [], "personal_catalog": []},
        )
        assert repeated.status_code == 200
        assert repeated.json()["stats"]["lists"] == 4


def test_shared_invitation_grants_only_selected_list() -> None:
    suffix = uuid4().hex
    owner_id = int(suffix[:14], 16)
    guest_id = int(suffix[14:28], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        owner, owner_headers = authenticate(client, owner_id, "Организатор")
        _, guest_headers = authenticate(client, guest_id, "Участник")
        shared_space = next(
            space for space in owner["spaces"]
            if space["kind"] == "shared" and space["title"] == "Совместно"
        )

        created_lists = []
        for title in ("Поход", "Секретный список"):
            response = client.post(
                f"/api/v1/spaces/{shared_space['id']}/lists",
                headers=owner_headers,
                json={"title": title, "category": "shared"},
            )
            assert response.status_code == 201, response.text
            created_lists.append(response.json())
        assert created_lists[0]["space_id"] != created_lists[1]["space_id"]

        invitation = client.post(
            f"/api/v1/lists/{created_lists[0]['id']}/invitations",
            headers=owner_headers,
        )
        assert invitation.status_code == 201, invitation.text
        invite = invitation.json()
        assert len(invite["code"]) == 8
        assert f"?start=join_{invite['code']}" in invite["bot_url"]

        accepted = client.post(
            f"/api/v1/invitations/{invite['code'].lower()}/accept",
            headers=guest_headers,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["joined"] is True
        accepted_again = client.post(
            f"/api/v1/invitations/{invite['code']}/accept",
            headers=guest_headers,
        )
        assert accepted_again.status_code == 200
        assert accepted_again.json()["joined"] is False

        guest_account = client.get("/api/v1/auth/session", headers=guest_headers).json()
        guest_shared_titles = {
            item["title"]
            for space in guest_account["spaces"]
            if space["kind"] == "shared"
            for item in space["lists"]
        }
        assert "Поход" in guest_shared_titles
        assert "Секретный список" not in guest_shared_titles
        assert client.get(
            f"/api/v1/lists/{created_lists[0]['id']}", headers=guest_headers
        ).status_code == 200
        assert client.patch(
            f"/api/v1/lists/{created_lists[0]['id']}",
            headers=guest_headers,
            json={"title": "Подмена"},
        ).status_code == 403
        left = client.delete(
            f"/api/v1/lists/{created_lists[0]['id']}", headers=guest_headers
        )
        assert left.status_code == 204, left.text
        assert client.get(
            f"/api/v1/lists/{created_lists[0]['id']}", headers=guest_headers
        ).status_code == 403
        assert client.get(
            f"/api/v1/lists/{created_lists[0]['id']}", headers=owner_headers
        ).status_code == 200
        assert client.get(
            f"/api/v1/lists/{created_lists[1]['id']}", headers=guest_headers
        ).status_code == 403


def test_shared_list_survives_creator_leaving_and_transfers_ownership() -> None:
    suffix = uuid4().hex
    owner_id = int(suffix[:10], 16)
    first_guest_id = int(suffix[10:20], 16)
    second_guest_id = int(suffix[20:30], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        owner, owner_headers = authenticate(client, owner_id, "Организатор")
        _, first_headers = authenticate(client, first_guest_id, "Первый участник")
        _, second_headers = authenticate(client, second_guest_id, "Второй участник")
        shared_space = next(
            space for space in owner["spaces"]
            if space["kind"] == "shared" and space["title"] == "Совместно"
        )
        created = client.post(
            f"/api/v1/spaces/{shared_space['id']}/lists",
            headers=owner_headers,
            json={"title": "Общий поход", "category": "shared"},
        )
        assert created.status_code == 201, created.text
        list_id = created.json()["id"]
        invitation = client.post(
            f"/api/v1/lists/{list_id}/invitations",
            headers=owner_headers,
        )
        assert invitation.status_code == 201, invitation.text
        code = invitation.json()["code"]
        for headers in (first_headers, second_headers):
            accepted = client.post(f"/api/v1/invitations/{code}/accept", headers=headers)
            assert accepted.status_code == 200, accepted.text

        removed_for_creator = client.delete(
            f"/api/v1/lists/{list_id}", headers=owner_headers
        )
        assert removed_for_creator.status_code == 204, removed_for_creator.text
        assert client.get(f"/api/v1/lists/{list_id}", headers=owner_headers).status_code == 403
        assert client.get(f"/api/v1/lists/{list_id}", headers=first_headers).status_code == 200
        assert client.get(f"/api/v1/lists/{list_id}", headers=second_headers).status_code == 200

        first_account = client.get("/api/v1/auth/session", headers=first_headers).json()
        transferred_space = next(
            space for space in first_account["spaces"]
            if any(item["id"] == list_id for item in space["lists"])
        )
        assert transferred_space["is_owner"] is True
        assert transferred_space["role"] == "owner"
        renamed = client.patch(
            f"/api/v1/lists/{list_id}",
            headers=first_headers,
            json={"title": "Поход продолжается"},
        )
        assert renamed.status_code == 200, renamed.text


def test_list_pins_are_personal_for_each_member() -> None:
    suffix = uuid4().hex
    owner_id = int(suffix[:14], 16)
    member_id = int(suffix[14:28], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        owner, owner_headers = authenticate(client, owner_id, "Владелец списка")
        _, member_headers = authenticate(client, member_id, "Участник списка")
        personal_space = next(space for space in owner["spaces"] if space["kind"] == "personal")
        asyncio.run(add_member_to_space(member_id, personal_space["id"]))
        created = client.post(
            f"/api/v1/spaces/{personal_space['id']}/lists",
            headers=owner_headers,
            json={"title": "Закрепить независимо", "category": "personal"},
        )
        assert created.status_code == 201, created.text
        list_id = created.json()["id"]

        owner_pin = client.put(
            f"/api/v1/lists/{list_id}/pin",
            headers=owner_headers,
            json={"pinned": True},
        )
        assert owner_pin.status_code == 200, owner_pin.text
        owner_account = client.get("/api/v1/auth/session", headers=owner_headers).json()
        member_account = client.get("/api/v1/auth/session", headers=member_headers).json()
        owner_list = next(
            item for space in owner_account["spaces"] for item in space["lists"]
            if item["id"] == list_id
        )
        member_list = next(
            item for space in member_account["spaces"] for item in space["lists"]
            if item["id"] == list_id
        )
        assert owner_list["is_pinned"] is True
        assert member_list["is_pinned"] is False

        member_pin = client.put(
            f"/api/v1/lists/{list_id}/pin",
            headers=member_headers,
            json={"pinned": True},
        )
        assert member_pin.status_code == 200, member_pin.text
        owner_unpin = client.put(
            f"/api/v1/lists/{list_id}/pin",
            headers=owner_headers,
            json={"pinned": False},
        )
        assert owner_unpin.status_code == 200, owner_unpin.text
        member_account = client.get("/api/v1/auth/session", headers=member_headers).json()
        member_list = next(
            item for space in member_account["spaces"] for item in space["lists"]
            if item["id"] == list_id
        )
        assert member_list["is_pinned"] is True


def test_family_owner_controls_members_and_member_keeps_old_lists() -> None:
    suffix = uuid4().hex
    owner_id = int(suffix[:14], 16)
    guest_id = int(suffix[14:28], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        owner, owner_headers = authenticate(client, owner_id, "Глава семьи")
        guest, guest_headers = authenticate(client, guest_id, "Будущий участник")
        owner_family = next(space for space in owner["spaces"] if space["kind"] == "family")
        guest_family = next(space for space in guest["spaces"] if space["kind"] == "family")

        family_list = client.post(
            f"/api/v1/spaces/{owner_family['id']}/lists",
            headers=owner_headers,
            json={"title": "Общие продукты", "category": "family"},
        )
        assert family_list.status_code == 201, family_list.text
        old_guest_list = client.post(
            f"/api/v1/spaces/{guest_family['id']}/lists",
            headers=guest_headers,
            json={"title": "Старый семейный список", "category": "family"},
        )
        assert old_guest_list.status_code == 201, old_guest_list.text

        invitation = client.post(
            f"/api/v1/families/{owner_family['id']}/invitations",
            headers=owner_headers,
        )
        assert invitation.status_code == 201, invitation.text
        assert len(invitation.json()["code"]) == 8
        accepted = client.post(
            f"/api/v1/invitations/{invitation.json()['code']}/accept",
            headers=guest_headers,
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["kind"] == "family"
        assert accepted.json()["joined"] is True

        guest_account = client.get("/api/v1/auth/session", headers=guest_headers).json()
        guest_families = [space for space in guest_account["spaces"] if space["kind"] == "family"]
        assert len(guest_families) == 1
        assert guest_families[0]["id"] == owner_family["id"]
        assert guest_families[0]["is_owner"] is False
        assert len(guest_families[0]["members"]) == 2
        personal_titles = {
            item["title"]
            for space in guest_account["spaces"]
            if space["kind"] == "personal"
            for item in space["lists"]
        }
        assert "Старый семейный список" in personal_titles

        member_add = client.post(
            f"/api/v1/lists/{family_list.json()['id']}/items",
            headers=guest_headers,
            json={"name": "Семейное молоко", "quantity": "1", "unit": "л"},
        )
        assert member_add.status_code == 201, member_add.text
        forbidden_invite = client.post(
            f"/api/v1/families/{owner_family['id']}/invitations",
            headers=guest_headers,
        )
        assert forbidden_invite.status_code == 422

        owner_account = client.get("/api/v1/auth/session", headers=owner_headers).json()
        owner_family_after = next(
            space for space in owner_account["spaces"] if space["id"] == owner_family["id"]
        )
        guest_member = next(
            member for member in owner_family_after["members"] if not member["is_current"]
        )
        removed = client.delete(
            f"/api/v1/families/{owner_family['id']}/members/{guest_member['id']}",
            headers=owner_headers,
        )
        assert removed.status_code == 204, removed.text
        guest_after_removal = client.get("/api/v1/auth/session", headers=guest_headers).json()
        new_guest_family = next(
            space for space in guest_after_removal["spaces"] if space["kind"] == "family"
        )
        assert new_guest_family["id"] != owner_family["id"]
        assert client.get(
            f"/api/v1/lists/{family_list.json()['id']}", headers=guest_headers
        ).status_code == 403
        assert any(
            item["title"] == "Старый семейный список"
            for space in guest_after_removal["spaces"]
            if space["kind"] == "personal"
            for item in space["lists"]
        )


def test_first_share_isolates_legacy_shared_lists() -> None:
    suffix = uuid4().hex
    owner_id = int(suffix[:14], 16)
    guest_id = int(suffix[14:28], 16)
    application = create_app(
        database_enabled=True,
        database_url=DATABASE_URL,
    )

    with TestClient(application) as client:
        _, owner_headers = authenticate(client, owner_id, "Старый владелец")
        _, guest_headers = authenticate(client, guest_id, "Новый участник")
        migrated = client.post(
            "/api/v1/migrations/local-storage",
            headers=owner_headers,
            json={
                "migration_id": f"legacy_shared_{suffix[:8]}",
                "lists": [
                    {"title": "Старый поход", "category": "shared", "items": []},
                    {"title": "Чужая закупка", "category": "shared", "items": []},
                ],
                "personal_catalog": [],
            },
        )
        assert migrated.status_code == 200, migrated.text
        legacy_lists = {
            item["title"]: item
            for space in migrated.json()["spaces"]
            if space["kind"] == "shared"
            for item in space["lists"]
        }
        invitation = client.post(
            f"/api/v1/lists/{legacy_lists['Старый поход']['id']}/invitations",
            headers=owner_headers,
        )
        assert invitation.status_code == 201, invitation.text
        accepted = client.post(
            f"/api/v1/invitations/{invitation.json()['code']}/accept",
            headers=guest_headers,
        )
        assert accepted.status_code == 200, accepted.text
        assert client.get(
            f"/api/v1/lists/{legacy_lists['Старый поход']['id']}", headers=guest_headers
        ).status_code == 200
        assert client.get(
            f"/api/v1/lists/{legacy_lists['Чужая закупка']['id']}", headers=guest_headers
        ).status_code == 403

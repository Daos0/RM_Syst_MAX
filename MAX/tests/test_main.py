import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app(database_enabled=False))


def test_mini_app() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Начать покупки" in response.text
    assert "Личный кабинет" in response.text
    assert "Семейная группа" in response.text
    assert "Методичка" in response.text
    assert "Как пользоваться списками" in response.text
    assert "Распределите покупки" in response.text
    assert "для 4 литров борща" in response.text
    assert "Новый владелец назначится автоматически" in response.text
    assert "Роман Михайлов" in response.text
    assert "Создаю сайты, Mini Apps, чат-ботов и AI-решения для бизнеса" in response.text
    assert "Последние списки" not in response.text
    assert "Добавить в список" in response.text
    assert "Единый поиск" in response.text
    assert "Товар, блюдо или для дома" in response.text
    assert "Куплено 0 из 0" in response.text
    assert "Открыть меню бота" not in response.text
    assert "Присоединиться к покупке" in response.text
    assert "Ссылка или код приглашения" in response.text
    assert "Поделиться покупкой" in response.text
    assert "Отметить всё купленным" in response.text
    assert 'class="nav-button nav-add-button"' in response.text
    assert 'id="nav-back"' in response.text
    assert 'id="open-list-manager"' in response.text
    assert "Добавить список" in response.text
    assert 'data-manager-add-goal="Для себя"' in response.text
    assert 'data-manager-add-goal="Для семьи"' in response.text
    assert 'data-manager-add-goal="Совместно"' in response.text
    assert "Главное меню" not in response.text
    assert 'href="/static/css/miniapp.css?' in response.text
    assert 'src="/static/js/app.js?' in response.text


def test_mini_app_assets() -> None:
    stylesheet = client.get("/static/css/miniapp.css")
    application_script = client.get("/static/js/app.js")
    catalog = client.get("/static/js/catalog.js")
    products = client.get("/static/js/products.js")
    grocery = client.get("/static/js/grocery.js")
    supplies = client.get("/static/js/supplies.js")
    catalog_api = client.get("/static/js/catalog-api.js")
    product_browser = client.get("/static/js/product-browser.js")
    unified_search = client.get("/static/js/unified-search.js")
    storage = client.get("/static/js/storage.js")
    server_api = client.get("/static/js/server-api.js")
    cabinet = client.get("/static/js/cabinet.js")
    list_actions = client.get("/static/js/list-actions.js")
    invite_entry = client.get("/static/js/invite-entry.js")
    list_sharing = client.get("/static/js/list-sharing.js")
    list_manager = client.get("/static/js/list-manager.js")
    list_realtime = client.get("/static/js/list-realtime.js")
    app_realtime = client.get("/static/js/app-realtime.js")
    platform_bridge = client.get("/static/js/platform-bridge.js")
    notifications = client.get("/static/js/notifications.js")

    assert stylesheet.status_code == 200
    assert ".selection-head" in stylesheet.text
    assert "align-items: center" in stylesheet.text
    assert "width: min(100%,520px)" in stylesheet.text
    assert "--visible-viewport-height" in stylesheet.text
    assert 'initial-scale=.70' in client.get("/").text
    assert application_script.status_code == 200
    assert "createShoppingRenderer" in application_script.text
    assert "createUnifiedSearch" in application_script.text
    assert "getElementById('add-product').addEventListener" in application_script.text
    assert "visualViewport" in client.get("/static/js/app-bootstrap.js").text
    assert catalog.status_code == 200
    assert "Овощи и фрукты" in catalog.text
    assert products.status_code == 200
    assert "catalogDefaults" in products.text
    assert grocery.status_code == 200
    assert "groceryGroups" in grocery.text
    assert supplies.status_code == 200
    assert "supplyGroups" in supplies.text
    assert catalog_api.status_code == 200
    assert "/api/v1/catalog" in catalog_api.text
    assert product_browser.status_code == 200
    assert "createProductBrowser" in product_browser.text
    assert unified_search.status_code == 200
    assert "createUnifiedSearch" in unified_search.text
    assert "recipeCatalog" not in unified_search.text
    assert "kind: 'dish'" not in unified_search.text
    assert storage.status_code == 200
    assert "storageKeys" in storage.text
    assert server_api.status_code == 200
    assert "/api/v1/auth/${platform}" in server_api.text
    assert "/api/v1/migrations/local-storage" in server_api.text
    assert "/api/v1/lists/${listId}/pin" in server_api.text
    assert cabinet.status_code == 200
    assert "createCabinet" in cabinet.text
    assert "createFamilyInvitation" in cabinet.text
    assert "setGuideOpen" in cabinet.text
    assert list_actions.status_code == 200
    assert "setAllItemsStatus" in list_actions.text
    assert "openAllLists" in cabinet.text
    assert invite_entry.status_code == 200
    assert "extractInviteCode" in invite_entry.text
    assert list_sharing.status_code == 200
    assert "createInvitation" in list_sharing.text
    assert list_manager.status_code == 200
    assert "onShareList" in list_manager.text
    assert "Редактировать списки" in list_manager.text
    assert "Закреплённые" in list_manager.text
    assert "priorityKinds" in list_manager.text
    assert "makeInlineAddButton" in list_manager.text
    assert "lists.length < 5" in list_manager.text
    assert "setManagerNavigation('Добавить', 'plus')" in list_manager.text
    assert "requestListRemoval" in list_manager.text
    assert "У присоединившихся участников он сохранится" in list_manager.text
    assert list_realtime.status_code == 200
    assert "EventSource" in list_realtime.text
    assert "list_changed" in list_realtime.text
    assert app_realtime.status_code == 200
    assert "initializeOpenListRealtime" in app_realtime.text
    assert platform_bridge.status_code == 200
    assert "telegram" in platform_bridge.text
    assert "openMessengerLink" in platform_bridge.text
    assert "dataset.telegramBotUsername" not in platform_bridge.text
    assert "DioMoneyBot" not in platform_bridge.text
    assert notifications.status_code == 200
    assert "createNotification" in notifications.text
    assert "ТЕСТ" not in notifications.text


def test_project_files_stay_below_line_limit() -> None:
    project_root = Path(__file__).resolve().parents[1]
    suffixes = {".py", ".js", ".css", ".html", ".json", ".md"}
    files = [
        path
        for root in (project_root / "app", project_root / "tests", project_root / "migrations")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes
    ]
    files.extend(
        path
        for name in ("AGENTS.md", "PLAN.md", "README.md")
        if (path := project_root / name).is_file()
    )
    violations = {
        str(path.relative_to(project_root)): len(path.read_text(encoding="utf-8").splitlines())
        for path in files
        if len(path.read_text(encoding="utf-8").splitlines()) > 1000
    }
    assert violations == {}


def test_health(monkeypatch) -> None:
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-token")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "max_configured": True,
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "database_configured": False,
        "database_ready": False,
    }


def test_realtime_requires_database() -> None:
    response = client.get("/api/v1/lists/00000000-0000-0000-0000-000000000001/events")
    assert response.status_code == 503

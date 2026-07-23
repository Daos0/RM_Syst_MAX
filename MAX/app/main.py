import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.db.session import Database

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

STATIC_DIR = Path(__file__).parent / "static"
MINI_APP_FILE = STATIC_DIR / "miniapp.html"


def create_app(
    *,
    database_enabled: bool | None = None,
    database_url: str | None = None,
) -> FastAPI:
    configured_database_url = database_url or os.getenv("DATABASE_URL")
    use_database = bool(configured_database_url) if database_enabled is None else database_enabled

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database: Database | None = None
        application.state.database = None
        application.state.database_ready = False
        try:
            if use_database:
                if not configured_database_url:
                    raise RuntimeError("DATABASE_URL is required")
                database = Database(configured_database_url)
                await database.ping()
                application.state.database = database
                application.state.database_ready = True
            yield
        finally:
            application.state.database_ready = False
            if database is not None:
                await database.dispose()
            application.state.database = None

    application = FastAPI(
        title="Shopping Assistant",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.database = None
    application.state.database_ready = False
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    application.include_router(api_router)

    @application.get("/", include_in_schema=False)
    async def mini_app():
        return FileResponse(MINI_APP_FILE, media_type="text/html")

    @application.get("/health")
    async def health():
        database_ready = bool(getattr(application.state, "database_ready", False))
        storage_ready = database_ready if use_database else True
        status_code = 200 if storage_ready else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if status_code == 200 else "not_ready",
                "max_configured": bool(os.getenv("MAX_BOT_TOKEN")),
                "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
                "database_configured": use_database,
                "database_ready": database_ready,
            },
        )

    return application


app = create_app()

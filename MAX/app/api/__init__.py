from fastapi import APIRouter

from app.api.catalog_routes import router as catalog_router
from app.api.auth_routes import router as auth_router
from app.api.assignment_routes import router as assignment_router
from app.api.list_action_routes import router as list_action_router
from app.api.list_preference_routes import router as list_preference_router
from app.api.family_routes import router as family_router
from app.api.invitation_routes import router as invitation_router
from app.api.routes import router as shopping_router
from app.api.migration_routes import router as migration_router
from app.api.realtime_routes import router as realtime_router
from app.api.admin_audience_routes import router as admin_audience_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(assignment_router)
router.include_router(list_action_router)
router.include_router(list_preference_router)
router.include_router(family_router)
router.include_router(invitation_router)
router.include_router(migration_router)
router.include_router(catalog_router)
router.include_router(realtime_router)
router.include_router(admin_audience_router)
router.include_router(shopping_router)

__all__ = ["router"]

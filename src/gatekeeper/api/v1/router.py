from fastapi import APIRouter

from gatekeeper.api.v1.admin import router as admin_router
from gatekeeper.api.v1.auth import router as auth_router
from gatekeeper.api.v1.security import router as security_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(security_router)

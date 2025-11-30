"""
API Routes - combines all route modules
"""

from api.health import router as health_router
from api.metrics import router as metrics_router
from api.process import router as process_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(process_router)
router.include_router(health_router)
router.include_router(metrics_router)

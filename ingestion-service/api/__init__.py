"""
API Routes - combines all route modules
"""

from api.health import router as health_router
from api.ingest import router as ingest_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(ingest_router)
router.include_router(health_router)

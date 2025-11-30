"""
Memory Machines Backend - Health Endpoint

GET /health - Returns service health status
"""

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str

    model_config = {
        "json_schema_extra": {
            "example": {"status": "healthy", "service": "worker", "version": "1.0.0"}
        }
    }


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Returns the health status of the service.",
    response_model=HealthResponse,
)
async def health():
    return HealthResponse(status="healthy", service="worker", version="1.0.0")

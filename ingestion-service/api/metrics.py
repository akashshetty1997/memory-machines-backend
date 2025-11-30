"""
Memory Machines Backend - Metrics Endpoint

GET /metrics - Returns basic per-instance runtime metrics.
"""

from fastapi import APIRouter
from metrics import snapshot

router = APIRouter(tags=["Metrics"])


@router.get(
    "/metrics",
    summary="Service metrics",
    description="Returns basic per-instance runtime metrics including uptime, request count, and last request time.",
    responses={
        200: {
            "description": "Metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "service": "ingestion",
                        "uptime_seconds": 3600,
                        "requests_total": 1500,
                        "last_request_at": "2025-11-30T19:00:00+00:00",
                    }
                }
            },
        },
    },
)
async def get_metrics():
    return snapshot()

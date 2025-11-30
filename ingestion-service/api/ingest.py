"""
Memory Machines Backend - Ingest Endpoint

POST /ingest - Accepts JSON or text/plain, publishes to Pub/Sub, returns 202
"""

import hashlib
import logging
from uuid import uuid4

from config import GCP_PROJECT_ID, MAX_TEXT_LENGTH, PUBSUB_TOPIC_ID, SCHEMA_VERSION
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.cloud import pubsub_v1
from response import APIResponse, ErrorCodes

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Global Pub/Sub client (reused across requests) ---
publisher = None
topic_path = ""


def get_publisher():
    global publisher, topic_path
    if publisher is None:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC_ID)
        logger.info(f"initialized publisher: {topic_path}")
    return publisher


def publish_callback(future, log_id):
    """Log publish failures (non-blocking callback)."""
    try:
        future.result(timeout=0)
    except Exception as e:
        logger.error(f"publish failed log_id={log_id}: {e}")


# --- Router ---
router = APIRouter(tags=["Ingestion"])


@router.post(
    "/ingest",
    summary="Ingest log data",
    description="""
Accepts log data in **JSON** or **plain text** format and queues it for async processing.

## JSON Format

Send a JSON body with `Content-Type: application/json`:
```json
{
    "tenant_id": "acme_corp",
    "log_id": "unique-log-123",
    "text": "User 555-0199 accessed the system at 10:00 AM"
}
```

## Plain Text Format

Send raw text with headers:
- `Content-Type: text/plain`
- `X-Tenant-ID: acme_corp`

Body contains the raw log text. A `log_id` will be auto-generated.

## Processing

Messages are queued in Pub/Sub and processed asynchronously by the worker service.
The worker simulates heavy processing (0.05s per character) before storing in Firestore.

## Tenant Isolation

Data is stored in tenant-isolated paths: `tenants/{tenant_id}/processed_logs/{log_id}`
    """,
    response_model=APIResponse,
    responses={
        202: {
            "description": "Message accepted and queued for processing",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {"status": "accepted", "log_id": "log-001"},
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request - missing or invalid fields",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "tenant_id required",
                        },
                    }
                }
            },
        },
        413: {
            "description": "Payload too large - text exceeds 5000 characters",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "text exceeds 5000 characters",
                        },
                    }
                }
            },
        },
        415: {
            "description": "Unsupported Content-Type",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNSUPPORTED_CONTENT_TYPE",
                            "message": "unsupported Content-Type",
                        },
                    }
                }
            },
        },
        503: {
            "description": "Service unavailable - failed to queue message",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "SERVICE_UNAVAILABLE",
                            "message": "failed to queue message",
                        },
                    }
                }
            },
        },
    },
)
async def ingest(request: Request):
    content_type = request.headers.get("content-type", "").lower()

    # Correlation ID: from header or generate
    correlation_id = request.headers.get("x-request-id") or str(uuid4())

    # --- Parse based on content type ---
    if content_type.startswith("application/json"):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.INVALID_JSON,
                        "message": "invalid JSON",
                    },
                },
                status_code=400,
            )

        tenant_id = body.get("tenant_id")
        log_id = body.get("log_id")
        text = body.get("text")
        source = "json_upload"

        if not tenant_id:
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.VALIDATION_ERROR,
                        "message": "tenant_id required",
                    },
                },
                status_code=400,
            )
        if not log_id:
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.VALIDATION_ERROR,
                        "message": "log_id required",
                    },
                },
                status_code=400,
            )
        if not text:
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.VALIDATION_ERROR,
                        "message": "text required",
                    },
                },
                status_code=400,
            )

    elif content_type.startswith("text/plain"):
        tenant_id = request.headers.get("x-tenant-id")
        if not tenant_id:
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.VALIDATION_ERROR,
                        "message": "X-Tenant-ID header required",
                    },
                },
                status_code=400,
            )

        text = (await request.body()).decode("utf-8", errors="replace")
        if not text.strip():
            return JSONResponse(
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": ErrorCodes.VALIDATION_ERROR,
                        "message": "text required",
                    },
                },
                status_code=400,
            )

        log_id = str(uuid4())
        source = "text_upload"

    else:
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.UNSUPPORTED_CONTENT_TYPE,
                    "message": "unsupported Content-Type",
                },
            },
            status_code=415,
        )

    # --- Validate text length ---
    if len(text) > MAX_TEXT_LENGTH:
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.PAYLOAD_TOO_LARGE,
                    "message": f"text exceeds {MAX_TEXT_LENGTH} characters",
                },
            },
            status_code=413,
        )

    # --- Compute content hash ---
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # --- Publish to Pub/Sub ---
    try:
        pub = get_publisher()
        future = pub.publish(
            topic_path,
            data=text.encode("utf-8"),
            tenant_id=tenant_id,
            log_id=log_id,
            source=source,
            content_hash=content_hash,
            schema_version=SCHEMA_VERSION,
            correlation_id=correlation_id,
        )
        future.add_done_callback(lambda f: publish_callback(f, log_id))

    except Exception as e:
        logger.error(f"publish exception: {e}")
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.SERVICE_UNAVAILABLE,
                    "message": "failed to queue message",
                },
            },
            status_code=503,
        )

    # --- Return 202 immediately ---
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "status": "accepted",
                "log_id": log_id,
                "correlation_id": correlation_id,
            },
            "error": None,
        },
        status_code=202,
    )

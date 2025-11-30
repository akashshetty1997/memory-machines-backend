"""
Memory Machines Backend - Process Endpoint

POST /process - Pub/Sub push handler, processes message, writes to Firestore
"""

import asyncio
import base64
import logging
from datetime import datetime, timezone

from config import SLEEP_PER_CHAR
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.cloud import firestore
from response import APIResponse, ErrorCodes
from schemas import ErrorResponse, PubSubEnvelope
from utils import redact_sensitive_data

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Firestore client ---
db = None


def get_db():
    global db
    if db is None:
        db = firestore.Client()
        logger.info("initialized firestore client")
    return db


# --- Router ---
router = APIRouter(tags=["Processing"])


@router.post(
    "/process",
    summary="Process log message",
    description="""
Pub/Sub push endpoint that processes incoming log messages.

**This endpoint is private** - only Pub/Sub can invoke it via authenticated push.

## Processing Steps

1. **Decode**: Base64 decode the message data
2. **Validate**: Check for required attributes (tenant_id, log_id)
3. **Idempotency**: Skip if same content_hash already exists
4. **Process**: Sleep for 0.05 seconds per character (simulates heavy processing)
5. **Redact**: Mask sensitive data (phone numbers, IPs, emails, SSNs)
6. **Store**: Write to Firestore at `tenants/{tenant_id}/processed_logs/{log_id}`

## Firestore Document
```json
{
    "source": "json_upload",
    "original_text": "User 555-0199 accessed...",
    "modified_data": "User [REDACTED] accessed...",
    "processed_at": "2025-11-30T10:00:00Z",
    "content_hash": "abc123..."
}
```

## Retry Behavior

- Returns `200` to acknowledge successful processing
- Returns `400` for invalid messages (won't retry)
- Returns `500` for transient errors (will retry)
    """,
    response_model=APIResponse,
    responses={
        200: {
            "description": "Message processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {"status": "processed", "log_id": "log-001"},
                        "error": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid message format",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "MISSING_ATTRIBUTES",
                            "message": "missing tenant_id or log_id",
                        },
                    }
                }
            },
        },
    },
)
async def process(request: Request):
    """
    Pub/Sub push handler.
    - Decodes message
    - Sleeps 0.05s per character
    - Writes to Firestore at tenants/{tenant_id}/processed_logs/{log_id}
    - Returns 200 to ack, non-2xx to trigger retry
    """
    try:
        envelope = await request.json()
    except Exception:
        logger.error("invalid JSON envelope")
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.INVALID_ENVELOPE,
                    "message": "invalid JSON envelope",
                },
            },
            status_code=400,
        )

    # --- Parse Pub/Sub push envelope ---
    message = envelope.get("message")
    if not message:
        logger.error("missing 'message' in envelope")
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.MISSING_MESSAGE,
                    "message": "missing 'message' in envelope",
                },
            },
            status_code=400,
        )

    # Decode base64 data
    data_b64 = message.get("data", "")
    try:
        text = base64.b64decode(data_b64).decode("utf-8")
    except Exception as e:
        logger.error(f"failed to decode message data: {e}")
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.INVALID_BASE64,
                    "message": "failed to decode message data",
                },
            },
            status_code=400,
        )

    # Extract attributes
    attrs = message.get("attributes", {})
    tenant_id = attrs.get("tenant_id")
    log_id = attrs.get("log_id")
    source = attrs.get("source", "unknown")
    content_hash = attrs.get("content_hash", "")
    correlation_id = attrs.get("correlation_id", "")

    if not tenant_id or not log_id:
        logger.error(f"missing tenant_id or log_id: {attrs}")
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.MISSING_ATTRIBUTES,
                    "message": "missing tenant_id or log_id",
                },
            },
            status_code=400,
        )

    # --- Idempotency check & Firestore write ---
    db_client = get_db()
    doc_ref = (
        db_client.collection("tenants")
        .document(tenant_id)
        .collection("processed_logs")
        .document(log_id)
    )

    try:
        # Idempotency: check existing document if we have a content_hash
        if content_hash:
            existing = doc_ref.get()
            if existing.exists:
                existing_hash = existing.to_dict().get("content_hash", "")
                if existing_hash == content_hash:
                    logger.info(f"skip duplicate: tenant={tenant_id} log_id={log_id}")
                    return JSONResponse(
                        content={
                            "success": True,
                            "data": {
                                "status": "skipped",
                                "log_id": log_id,
                                "reason": "duplicate",
                            },
                            "error": None,
                        },
                        status_code=200,
                    )

        # --- Simulate heavy processing (PDF requirement: 0.05s per char) ---
        sleep_duration = len(text) * SLEEP_PER_CHAR
        logger.info(
            f"processing: tenant={tenant_id} log_id={log_id} "
            f"correlation_id={correlation_id} chars={len(text)} "
            f"sleep={sleep_duration:.2f}s"
        )
        await asyncio.sleep(sleep_duration)

        # --- Apply redaction ---
        redacted_text = redact_sensitive_data(text)

        # --- Write to Firestore (tenant-isolated path) ---
        doc_data = {
            "source": source,
            "original_text": text,
            "modified_data": redacted_text,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
            "correlation_id": correlation_id,
        }
        doc_ref.set(doc_data)

    except Exception as exc:
        logger.exception(
            "firestore operation failed",
            extra={"tenant_id": tenant_id, "log_id": log_id},
        )
        return JSONResponse(
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": ErrorCodes.PROCESSING_ERROR,
                    "message": "failed to persist processed log",
                },
            },
            status_code=500,
        )

    logger.info(
        f"stored: tenants/{tenant_id}/processed_logs/{log_id} " f"correlation_id={correlation_id}"
    )
    return JSONResponse(
        content={
            "success": True,
            "data": {"status": "processed", "log_id": log_id},
            "error": None,
        },
        status_code=200,
    )

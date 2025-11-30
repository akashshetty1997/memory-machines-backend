"""
Memory Machines Backend - Ingestion Service

Application entry point. Sets up FastAPI app and includes all routes.
"""

import logging

from api import router
from config import API_VERSION, SERVICE_DESCRIPTION, SERVICE_NAME
from fastapi import FastAPI, Request
from metrics import record_request

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --- App ---
app = FastAPI(
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=API_VERSION,
)


# --- Metrics middleware ---
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    response = await call_next(request)
    record_request(request.url.path)
    return response


# --- Include routes ---
app.include_router(router)

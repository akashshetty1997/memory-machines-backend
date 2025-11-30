"""
Memory Machines Backend - Ingestion Service

Application entry point. Sets up FastAPI app and includes all routes.
"""

import logging

from api import router
from config import API_VERSION, SERVICE_DESCRIPTION, SERVICE_NAME
from fastapi import FastAPI

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --- App ---
app = FastAPI(
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=API_VERSION,
)

# --- Include routes ---
app.include_router(router)

"""
Memory Machines Backend - Ingestion Service Configuration

All environment variables, constants, and settings in one place.
"""

import os

# --- GCP Configuration ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
PUBSUB_TOPIC_ID = os.environ.get("PUBSUB_TOPIC_ID", "ingestion-topic")

# --- API Configuration ---
API_VERSION = "1.0.0"
SCHEMA_VERSION = "1"

# --- Validation Limits ---
MAX_TEXT_LENGTH = 5000

# --- Service Info ---
SERVICE_NAME = "Memory Machines Ingestion API"
SERVICE_DESCRIPTION = """
## Overview
Unified ingestion gateway for multi-tenant log processing.

## Supported Formats
- **JSON**: Structured data with tenant_id, log_id, and text
- **Text/Plain**: Raw text with tenant ID in header

## Features
- Non-blocking async processing
- Multi-tenant data isolation
- Handles 1000+ requests per minute
- Automatic crash recovery via message queue
"""

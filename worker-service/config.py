"""
Memory Machines Backend - Worker Service Configuration

All environment variables, constants, and settings in one place.
"""

import os

# --- Processing Configuration ---
SLEEP_PER_CHAR = 0.05  # seconds per character (PDF requirement: 0.05s)

# --- API Configuration ---
API_VERSION = "1.0.0"

# --- Service Info ---
SERVICE_NAME = "Memory Machines Worker Service"
SERVICE_DESCRIPTION = """
## Overview
Worker service that processes log messages from Pub/Sub.

## Features
- Simulates heavy processing (0.05s per character)
- Writes to Firestore with tenant isolation
- Supports crash recovery via Pub/Sub retries
"""

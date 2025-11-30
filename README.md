# Memory Machines Backend

A scalable, robust API backend for ingesting massive streams of unstructured logs from diverse sources. Built with a multi-tenant, event-driven pipeline on Google Cloud Platform.

## Live URL

```text
https://ingestion-555551574544.us-central1.run.app
```

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEMORY MACHINES BACKEND                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                │
│   │   Client    │      │   Client    │      │   Client    │                │
│   │   (JSON)    │      │(text/plain) │      │   (JSON)    │                │
│   └──────┬──────┘      └──────┬──────┘      └──────┬──────┘                │
│          │                    │                    │                        │
│          └────────────────────┼────────────────────┘                        │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │  POST /ingest       │                                  │
│                    │  (Cloud Run)        │                                  │
│                    │  - Validates input  │                                  │
│                    │  - Normalizes data  │                                  │
│                    │  - Returns 202      │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │  Pub/Sub Topic      │                                  │
│                    │  (ingestion-topic)  │◄──────┐                          │
│                    └──────────┬──────────┘       │                          │
│                               │                  │ Retry on                 │
│                               ▼                  │ failure                  │
│                    ┌─────────────────────┐       │                          │
│                    │  Worker Service     │───────┘                          │
│                    │  (Cloud Run)        │                                  │
│                    │  - Processes msgs   │                                  │
│                    │  - Sleeps 0.05s/chr │                                  │
│                    │  - Redacts PII      │                                  │
│                    │  - Writes Firestore │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                             │
│                               │ After 5 failed attempts                     │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │  Dead Letter Queue  │                                  │
│                    │  (ingestion-dlq)    │                                  │
│                    └─────────────────────┘                                  │
│                                                                             │
│                               │                                             │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │  Firestore          │                                  │
│                    │  (tenant isolated)  │                                  │
│                    │                     │                                  │
│                    │  tenants/           │                                  │
│                    │    ├── acme_corp/   │                                  │
│                    │    │   └── processed_logs/                             │
│                    │    └── beta_inc/    │                                  │
│                    │        └── processed_logs/                             │
│                    └─────────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Getting Started

There are three ways to run this project:

1. Local Python (dev only)
2. Docker (local containers)
3. Full GCP deployment (Cloud Run + Pub/Sub + Firestore)

### 1. Local Python (Dev Only)

This is enough to run the HTTP servers locally. Any code that talks to Pub/Sub / Firestore still needs real GCP credentials or emulators.

#### Prerequisites

- Python 3.11
- `pip`
- (Optional) `virtualenv` or `python -m venv`

#### 1.1. Ingestion Service

```bash
git clone https://github.com/akashshetty1997/memory-machines-backend.git
cd memory-machines-backend/ingestion-service

python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

Set environment variables (based on `.env.example`):

```bash
set GCP_PROJECT_ID=your-gcp-project-id
set PUBSUB_TOPIC_ID=ingestion-topic
# Optional for local use:
set GCP_REGION=us-central1
```

Run the API locally:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Now `/ingest`, `/health`, and `/metrics` are available on:

```text
http://localhost:8080/ingest
http://localhost:8080/health
http://localhost:8080/metrics
```

#### 1.2. Worker Service

```bash
cd ../worker-service

python -m venv venv
venv\Scripts\activate  # or source venv/bin/activate
pip install -r requirements.txt
```

Set environment variables (if needed):

```bash
set GCP_PROJECT_ID=your-gcp-project-id
```

Run the worker API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

The worker's `/process` endpoint is now listening at:

```text
http://localhost:8081/process
```

> Note: `/process` expects Pub/Sub push envelopes. For local testing, you can `curl` it with a fake envelope (see `tests/test_process.py` for the JSON shape).

---

### 2. Docker (Local Containers)

Both services have a Dockerfile.

#### 2.1. Build images

From the project root:

```bash
# Ingestion
docker build -t ingestion-service ./ingestion-service

# Worker
docker build -t worker-service ./worker-service
```

#### 2.2. Run containers

You must pass the same env vars used in Cloud Run:

```bash
# Ingestion
docker run --rm -p 8080:8080 \
  -e GCP_PROJECT_ID=your-gcp-project-id \
  -e PUBSUB_TOPIC_ID=ingestion-topic \
  ingestion-service

# Worker
docker run --rm -p 8081:8081 \
  -e GCP_PROJECT_ID=your-gcp-project-id \
  worker-service
```

If you want them to actually talk to real Pub/Sub / Firestore from your machine, you also need GCP credentials inside the container (for example, mount a service-account key and set `GOOGLE_APPLICATION_CREDENTIALS`).

#### 2.3. Docker Compose (local dev)

From the project root:

```bash
docker compose up --build
```

Ingestion: http://localhost:8080/docs

Worker: http://localhost:8081/docs

---

### 3. Full GCP Deployment (Recommended)

This is the path used for the real system (Cloud Run, Pub/Sub, Firestore).

#### Prerequisites

* `gcloud` CLI installed and authenticated
* GCP project with billing enabled

You can use either the batch script or the Makefile.

#### Option A: Using the setup script (Windows)

From the project root:

```bash
setup.bat
```

The script will:

1. Set the GCP project.
2. Enable required APIs.
3. Create Firestore DB, Pub/Sub topics, and service account.
4. Deploy ingestion and worker services to Cloud Run.
5. Wire Pub/Sub → worker via a push subscription.

At the end it prints the ingestion and worker URLs and a ready-to-run `curl` command.

#### Option B: Using Makefile (macOS/Linux)

```bash
make setup      # one-time infra setup
make deploy     # deploy ingestion + worker + wire Pub/Sub
```

After deploy, you can run:

```bash
make quick-test
```

to send a couple of sample requests to `/ingest`.

---

### Environment Variables

The project does **not** require a `.env` file in production. Cloud Run injects env vars directly via `--set-env-vars`.

For local development, you can create a `.env` file based on `.env.example`:

```env
# .env.example
GCP_PROJECT_ID=your-gcp-project-id
PUBSUB_TOPIC_ID=ingestion-topic
GCP_REGION=us-central1
INGESTION_URL=https://ingestion-xxxxx.us-central1.run.app
WORKER_URL=https://worker-xxxxx.us-central1.run.app
```

If you want `.env` to be used automatically, you can add `python-dotenv` and a `load_dotenv()` call in `main.py`, but it's optional.

## API Endpoint

### POST `/ingest`

Accepts log data and queues it for async processing. Returns immediately with `202 Accepted` after publishing to Pub/Sub.

#### JSON Format

```bash
curl -X POST https://ingestion-555551574544.us-central1.run.app/ingest \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme_corp","log_id":"123","text":"User accessed system"}'
```

#### Plain Text Format

```bash
curl -X POST https://ingestion-555551574544.us-central1.run.app/ingest \
  -H "Content-Type: text/plain" \
  -H "X-Tenant-ID: acme_corp" \
  -d "2025-11-30 ERROR: Connection timeout on db-01"
```

#### Correlation ID (Request Tracing)

* If the client sends `X-Request-Id`, that value is propagated end-to-end:

  * `/ingest` logs
  * Pub/Sub attributes
  * Worker logs
  * Firestore document
* If the header is missing, the service generates a UUIDv4.

The correlation ID is always included in the response as `data.correlation_id`.

#### Response

```json
{
  "success": true,
  "data": {
    "status": "accepted",
    "log_id": "123",
    "correlation_id": "34bb0730-90e0-4b23-a98b-353c6adfee68"
  },
  "error": null
}
```

Status code: `202 Accepted`

## How JSON and TXT Paths Merge

Both input formats are normalized into the same internal format before being published to Pub/Sub:

```text
┌──────────────────┐     ┌──────────────────┐
│  JSON Request    │     │  Text Request    │
│                  │     │                  │
│  Content-Type:   │     │  Content-Type:   │
│  application/json│     │  text/plain      │
│                  │     │                  │
│  {               │     │  X-Tenant-ID:    │
│   "tenant_id":..,│     │  acme_corp       │
│   "log_id":...,  │     │                  │
│   "text":...     │     │  Body: raw text  │
│  }               │     │                  │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └───────────┬────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Normalized Format  │
          │                     │
          │  Pub/Sub Message:   │
          │  - data: text bytes │
          │  - attributes:      │
          │    - tenant_id      │
          │    - log_id         │
          │    - source         │
          │    - content_hash   │
          │    - correlation_id │
          │    - schema_version │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Worker Service     │
          │  (same processing)  │
          └─────────────────────┘
```

* For `application/json`, the client provides `log_id`.
* For `text/plain`, the service generates a `log_id` and returns it.

## Multi-Tenant Architecture

Data is strictly isolated using Firestore subcollections:

```text
tenants/
├── acme_corp/
│   └── processed_logs/
│       ├── log-001
│       └── log-002
├── beta_inc/
│   └── processed_logs/
│       └── log-003
└── gamma_llc/
    └── processed_logs/
        └── log-004
```

Each tenant’s data is physically separated at the path level. There is no way for one tenant to access another tenant’s data.

## Data Redaction

The worker automatically redacts sensitive information before storing:

| Type            | Example Input                   | Output       |
| --------------- | ------------------------------- | ------------ |
| Phone numbers   | `555-0199`, `(555) 123-4567`    | `[REDACTED]` |
| IP addresses    | `192.168.1.100`, `203.0.113.42` | `[REDACTED]` |
| Email addresses | `user@example.com`              | `[REDACTED]` |
| SSN             | `123-45-6789`                   | `[REDACTED]` |

**Example:**

* `original_text`: `User 555-0199 accessed from IP 192.168.1.100`
* `modified_data`: `User [REDACTED] accessed from IP [REDACTED]`

This matches the PDF example output.

## Crash Recovery / Chaos Handling

The system handles crashes gracefully through Pub/Sub’s built-in retry mechanism:

### How It Works

1. **Message Published**: Ingestion service publishes to `ingestion-topic`.
2. **Worker Receives**: Pub/Sub pushes message to worker.
3. **If Worker Fails**: Returns non-2xx status code.
4. **Pub/Sub Retries**: Automatically retries with exponential backoff.
5. **After 5 Failures**: Message moves to Dead Letter Queue (`ingestion-dlq`).

### Configuration

* **Ack Deadline**: 600 seconds (allows for long processing).
* **Max Delivery Attempts**: 5
* **Dead Letter Topic**: `ingestion-dlq`

### Idempotency

The worker uses `content_hash` to detect duplicate messages:

* If a document with the same `log_id` and `content_hash` already exists under the same tenant, the worker:

  * Skips processing.
  * Returns `status: "skipped", reason: "duplicate"`.

This prevents duplicate writes during Pub/Sub retries.

## Project Structure

```text
memory-machines-backend/
├── ingestion-service/
│   ├── api/
│   │   ├── __init__.py
│   │   └── ingest.py
│   ├── health.py
│   ├── metrics.py
│   ├── config.py
│   ├── response.py
│   ├── schemas.py
│   ├── utils.py
│   ├── main.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_ingest.py
│       └── test_utils.py
├── worker-service/
│   ├── api/
│   │   ├── __init__.py
│   │   └── process.py
│   ├── health.py
│   ├── metrics.py
│   ├── config.py
│   ├── response.py
│   ├── schemas.py
│   ├── utils.py
│   ├── main.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_process.py
│       └── test_utils.py
├── load_test.py
└── README.md
```

## Load Test Results

`load_test.py` is a small async load generator using `aiohttp`. It supports URL, RPM, duration, and concurrency.

Example:

```bash
python load_test.py https://ingestion-555551574544.us-central1.run.app/ingest \
  --rpm 1000 \
  --duration 60 \
  --concurrency 100
```

Sample run:

```text
Target: 1000 requests over 60s (1000 req/min, concurrency=100)

=== Results ===
Total requests: 1000
202 Accepted : 1000

Total time: 51.42s
Effective rate: 19.4 req/sec

Latency (for 202 responses):
  avg : 0.052s
  p50 : 0.049s
  p95 : 0.059s
  p99 : 0.065s
```

The service also successfully handled a short burst at an effective rate equivalent to ~2000 req/min with 100% `202 Accepted` responses.

## GCP Services Used

| Service           | Purpose                                    |
| ----------------- | ------------------------------------------ |
| Cloud Run         | Serverless compute for both services       |
| Pub/Sub           | Message queue between ingestion and worker |
| Firestore         | NoSQL database with tenant isolation       |
| Cloud Build       | Docker image builds                        |
| Artifact Registry | Container image storage                    |

## API Response Format

All endpoints return a standardized JSON response.

### Success Response

```json
{
  "success": true,
  "data": {
    "status": "accepted",
    "log_id": "log-001",
    "correlation_id": "34bb0730-90e0-4b23-a98b-353c6adfee68"
  },
  "error": null
}
```

### Error Response

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "tenant_id required"
  }
}
```

### Error Codes

| Code                       | Description                                               | HTTP Status |
| -------------------------- | --------------------------------------------------------- | ----------- |
| `VALIDATION_ERROR`         | Missing or invalid request fields                         | 400         |
| `INVALID_JSON`             | Request body is not valid JSON                            | 400         |
| `UNSUPPORTED_CONTENT_TYPE` | `Content-Type` must be `application/json` or `text/plain` | 415         |
| `PAYLOAD_TOO_LARGE`        | Text exceeds 5000 characters                              | 413         |
| `SERVICE_UNAVAILABLE`      | Failed to queue message to Pub/Sub                        | 503         |
| `INVALID_ENVELOPE`         | Worker received invalid Pub/Sub envelope                  | 400         |
| `MISSING_MESSAGE`          | Worker envelope missing `message`                         | 400         |
| `MISSING_ATTRIBUTES`       | Worker message missing `tenant_id` or `log_id`            | 400         |
| `INVALID_BASE64`           | Worker failed to base64-decode `data`                     | 400         |
| `PROCESSING_ERROR`         | Worker failed to persist processed log                    | 500         |

## Health Check

### Ingestion Service

```bash
curl https://ingestion-555551574544.us-central1.run.app/health
```

Sample response:

```json
{
  "status": "healthy",
  "service": "ingestion",
  "version": "1.0.0"
}
```

### Worker Service

Worker health endpoint is private, but exposes a similar JSON payload for internal checks.

## Metrics

### Ingestion Service

```bash
curl https://ingestion-555551574544.us-central1.run.app/metrics
```

Sample response:

```json
{
  "service": "ingestion",
  "uptime_seconds": 245,
  "requests_total": 3,
  "last_request_at": "2025-11-30T21:42:01.856052+00:00"
}
```

This endpoint exposes basic per-instance runtime metrics (uptime, total requests, last request time) for quick inspection. Metrics are per-process and complement platform-level monitoring.

## Running Tests

### Ingestion Service

```bash
cd ingestion-service
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pytest tests/ -v
```

### Worker Service

```bash
cd worker-service
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pytest tests/ -v
```

### Load Test

From the project root:

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install aiohttp
python load_test.py https://ingestion-555551574544.us-central1.run.app/ingest --rpm 1000 --duration 60
```

## Code Quality

This project is designed to work well with standard Python tooling:

* **Black** – code formatting
* **isort** – import sorting
* **Pylint** – static analysis
* **pytest** – testing

You can wire these via `pre-commit` and/or CI if desired.

## Deployment

### Prerequisites

* Google Cloud SDK (`gcloud`) installed
* GCP project with billing enabled
* Firestore in **native** mode

### Deploy Ingestion Service

```bash
cd ingestion-service
gcloud run deploy ingestion \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=<project-id>,PUBSUB_TOPIC_ID=ingestion-topic"
```

### Deploy Worker Service

```bash
cd worker-service
gcloud run deploy worker \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated \
  --timeout 600
```

### Wire Pub/Sub to Worker

```bash
gcloud pubsub topics create ingestion-topic
gcloud pubsub topics create ingestion-dlq

gcloud pubsub subscriptions create worker-push-sub \
  --topic ingestion-topic \
  --push-endpoint "https://<worker-url>/process" \
  --push-auth-service-account "<invoker-sa>@<project>.iam.gserviceaccount.com" \
  --ack-deadline 600 \
  --dead-letter-topic ingestion-dlq \
  --max-delivery-attempts 5
```

## Swagger Documentation

Access the API documentation at:

```text
https://ingestion-555551574544.us-central1.run.app/docs
```

# Memory Machines Backend

A scalable, robust API backend for ingesting massive streams of unstructured logs from diverse sources. Built with a multi-tenant, event-driven pipeline on Google Cloud Platform.

## Live URL

```
https://ingestion-555551574544.us-central1.run.app
```

## Architecture

```
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

## API Endpoint

### POST /ingest

Accepts log data and queues it for async processing.

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

#### Response

```json
{ "status": "accepted", "log_id": "123" }
```

Status code: `202 Accepted`

## How JSON and TXT Paths Merge

Both input formats are normalized into the same internal format before being published to Pub/Sub:

```
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
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  Worker Service     │
          │  (same processing)  │
          └─────────────────────┘
```

## Multi-Tenant Architecture

Data is strictly isolated using Firestore subcollections:

```
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

Each tenant's data is physically separated at the path level. There is no way for one tenant to access another tenant's data.

## Data Redaction

The worker automatically redacts sensitive information before storing:

| Type            | Example Input                   | Output       |
| --------------- | ------------------------------- | ------------ |
| Phone numbers   | `555-0199`, `(555) 123-4567`    | `[REDACTED]` |
| IP addresses    | `192.168.1.100`, `203.0.113.42` | `[REDACTED]` |
| Email addresses | `user@example.com`              | `[REDACTED]` |
| SSN             | `123-45-6789`                   | `[REDACTED]` |

**Example:**

- `original_text`: "User 555-0199 accessed from IP 192.168.1.100"
- `modified_data`: "User [REDACTED] accessed from IP [REDACTED]"

This matches the PDF example output exactly.

## Crash Recovery / Chaos Handling

The system handles crashes gracefully through Pub/Sub's built-in retry mechanism:

### How It Works

1. **Message Published**: Ingestion service publishes to `ingestion-topic`
2. **Worker Receives**: Pub/Sub pushes message to worker
3. **If Worker Fails**: Returns non-2xx status code
4. **Pub/Sub Retries**: Automatically retries with exponential backoff
5. **After 5 Failures**: Message moves to Dead Letter Queue (`ingestion-dlq`)

### Configuration

- **Ack Deadline**: 600 seconds (allows for long processing)
- **Max Delivery Attempts**: 5
- **Dead Letter Topic**: `ingestion-dlq`

### Idempotency

The worker uses `content_hash` to detect duplicate messages:

- If a message with the same `log_id` and `content_hash` already exists, it skips processing
- This prevents duplicate writes during retries

## Project Structure

```
memory-machines-backend/
├── ingestion-service/
│   ├── api/
│   │   ├── __init__.py
│   │   └── ingest.py
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── worker-service/
│   ├── api/
│   │   ├── __init__.py
│   │   └── process.py
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── scripts/
│   ├── load_test.py
│   └── requirements.txt
└── README.md
```

## Load Test Results

Tested at 1000 requests per minute for 60 seconds:

```
=== Results ===
202 Accepted: 999
4xx errors:   0
5xx errors:   0
Timeouts:     1

Avg latency:  105.1ms
p50 latency:  101.1ms
p99 latency:  324.2ms

Success rate: 99.9%
✓ PASS: Flood test passed
```

## GCP Services Used

| Service           | Purpose                                    |
| ----------------- | ------------------------------------------ |
| Cloud Run         | Serverless compute for both services       |
| Pub/Sub           | Message queue between ingestion and worker |
| Firestore         | NoSQL database with tenant isolation       |
| Cloud Build       | Docker image builds                        |
| Artifact Registry | Container image storage                    |

## Deployment

### Prerequisites

- Google Cloud SDK (`gcloud`) installed
- GCP project with billing enabled

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

```
https://ingestion-555551574544.us-central1.run.app/docs
```

```

```

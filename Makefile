# Memory Machines Backend - Makefile
# Usage: make setup | make deploy | make test | make load-test

PROJECT_ID := memory-machines-backend-479818
REGION := us-central1
INGESTION_URL := https://ingestion-555551574544.us-central1.run.app

.PHONY: setup deploy test load-test clean

# Full setup - run once
setup:
	@echo "Setting up GCP infrastructure..."
	gcloud config set project $(PROJECT_ID)
	gcloud services enable run.googleapis.com pubsub.googleapis.com firestore.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
	gcloud firestore databases create --location=$(REGION) || true
	gcloud pubsub topics create ingestion-topic || true
	gcloud pubsub topics create ingestion-dlq || true
	gcloud iam service-accounts create pubsub-invoker --display-name="Pub/Sub to Cloud Run Invoker" || true
	@echo "Infrastructure ready!"

# Deploy both services
deploy: deploy-ingestion deploy-worker wire-pubsub
	@echo "Deployment complete!"

deploy-ingestion:
	@echo "Deploying ingestion service..."
	cd ingestion-service && gcloud run deploy ingestion --source . --region $(REGION) --allow-unauthenticated --set-env-vars "GCP_PROJECT_ID=$(PROJECT_ID),PUBSUB_TOPIC_ID=ingestion-topic" --memory 512Mi --cpu 1 --concurrency 100 --timeout 60

deploy-worker:
	@echo "Deploying worker service..."
	cd worker-service && gcloud run deploy worker --source . --region $(REGION) --no-allow-unauthenticated --timeout 600 --memory 512Mi --cpu 1 --concurrency 10

wire-pubsub:
	@echo "Wiring Pub/Sub to worker..."
	$(eval WORKER_URL := $(shell gcloud run services describe worker --region $(REGION) --format "value(status.url)"))
	$(eval PROJECT_NUMBER := $(shell gcloud projects describe $(PROJECT_ID) --format "value(projectNumber)"))
	gcloud run services add-iam-policy-binding worker --region $(REGION) --member "serviceAccount:pubsub-invoker@$(PROJECT_ID).iam.gserviceaccount.com" --role "roles/run.invoker"
	-gcloud pubsub subscriptions delete worker-push-sub --quiet
	gcloud pubsub subscriptions create worker-push-sub --topic ingestion-topic --push-endpoint "$(WORKER_URL)/process" --push-auth-service-account "pubsub-invoker@$(PROJECT_ID).iam.gserviceaccount.com" --ack-deadline 600 --dead-letter-topic ingestion-dlq --max-delivery-attempts 5
	gcloud pubsub topics add-iam-policy-binding ingestion-dlq --member "serviceAccount:service-$(PROJECT_NUMBER)@gcp-sa-pubsub.iam.gserviceaccount.com" --role "roles/pubsub.publisher"
	gcloud pubsub subscriptions add-iam-policy-binding worker-push-sub --member "serviceAccount:service-$(PROJECT_NUMBER)@gcp-sa-pubsub.iam.gserviceaccount.com" --role "roles/pubsub.subscriber"

# Run unit tests
test: test-ingestion test-worker
	@echo "All tests passed!"

test-ingestion:
	@echo "Testing ingestion service..."
	cd ingestion-service && pip install -r requirements.txt && pytest tests/ -v

test-worker:
	@echo "Testing worker service..."
	cd worker-service && pip install -r requirements.txt && pytest tests/ -v

# Run load test
load-test:
	@echo "Running load test (1000 RPM for 60s)..."
	cd scripts && pip install -r requirements.txt && python load_test.py $(INGESTION_URL) --rpm 1000 --duration 60

# Quick API test
quick-test:
	@echo "Testing JSON endpoint..."
	curl -X POST $(INGESTION_URL)/ingest -H "Content-Type: application/json" -d '{"tenant_id":"acme","log_id":"test-001","text":"Hello from Makefile"}'
	@echo ""
	@echo "Testing text/plain endpoint..."
	curl -X POST $(INGESTION_URL)/ingest -H "Content-Type: text/plain" -H "X-Tenant-ID: beta" -d "Hello from text plain"
	@echo ""

# Clean up (use with caution)
clean:
	@echo "Cleaning up GCP resources..."
	-gcloud pubsub subscriptions delete worker-push-sub --quiet
	-gcloud run services delete ingestion --region $(REGION) --quiet
	-gcloud run services delete worker --region $(REGION) --quiet
	@echo "Cleanup complete!"

@echo off
setlocal enabledelayedexpansion

echo ============================================
echo Memory Machines Backend - Setup Script
echo ============================================

rem CHANGE THESE IF YOU COPY TO ANOTHER PROJECT
set PROJECT_ID=memory-machines-backend-479818
set REGION=us-central1
rem Firestore location is NOT a Cloud Run region; use a valid Firestore location like nam5
set FIRESTORE_LOCATION=nam5

echo.
echo [1/7] Setting GCP project...
call gcloud config set project %PROJECT_ID%

echo.
echo [2/7] Enabling APIs...
call gcloud services enable ^
    run.googleapis.com ^
    pubsub.googleapis.com ^
    firestore.googleapis.com ^
    artifactregistry.googleapis.com ^
    cloudbuild.googleapis.com

echo.
echo [3/7] Creating Firestore database...
rem This will fail if the DB already exists; we ignore stderr and print a friendly message.
call gcloud firestore databases create --location=%FIRESTORE_LOCATION% 2>nul || echo Firestore already exists

echo.
echo [4/7] Creating Pub/Sub topics...
call gcloud pubsub topics create ingestion-topic 2>nul || echo Topic 'ingestion-topic' already exists
call gcloud pubsub topics create ingestion-dlq 2>nul || echo Topic 'ingestion-dlq' already exists

echo.
echo [5/7] Creating service account...
call gcloud iam service-accounts create pubsub-invoker ^
    --display-name="Pub/Sub to Cloud Run Invoker" 2>nul || echo Service account 'pubsub-invoker' already exists

echo.
echo [6/7] Deploying ingestion service...
cd ingestion-service
call gcloud run deploy ingestion ^
    --source . ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --set-env-vars "GCP_PROJECT_ID=%PROJECT_ID%,PUBSUB_TOPIC_ID=ingestion-topic" ^
    --memory 512Mi ^
    --cpu 1 ^
    --concurrency 100 ^
    --timeout 60
cd ..

echo.
echo [7/7] Deploying worker service...
cd worker-service
call gcloud run deploy worker ^
    --source . ^
    --region %REGION% ^
    --no-allow-unauthenticated ^
    --timeout 600 ^
    --memory 512Mi ^
    --cpu 1 ^
    --concurrency 10
cd ..

echo.
echo Getting service URLs...
for /f "tokens=*" %%i in ('
    gcloud run services describe ingestion --region %REGION% --format "value(status.url)"
') do set INGESTION_URL=%%i

for /f "tokens=*" %%i in ('
    gcloud run services describe worker --region %REGION% --format "value(status.url)"
') do set WORKER_URL=%%i

echo.
echo Granting invoker permission on worker...
call gcloud run services add-iam-policy-binding worker ^
    --region %REGION% ^
    --member "serviceAccount:pubsub-invoker@%PROJECT_ID%.iam.gserviceaccount.com" ^
    --role "roles/run.invoker"

echo.
echo Creating Pub/Sub subscription (worker-push-sub)...
call gcloud pubsub subscriptions delete worker-push-sub --quiet 2>nul
call gcloud pubsub subscriptions create worker-push-sub ^
    --topic ingestion-topic ^
    --push-endpoint "%WORKER_URL%/process" ^
    --push-auth-service-account "pubsub-invoker@%PROJECT_ID%.iam.gserviceaccount.com" ^
    --ack-deadline 600 ^
    --dead-letter-topic ingestion-dlq ^
    --max-delivery-attempts 5

echo.
echo Granting DLQ permissions...
for /f "tokens=*" %%i in ('
    gcloud projects describe %PROJECT_ID% --format "value(projectNumber)"
') do set PROJECT_NUMBER=%%i

call gcloud pubsub topics add-iam-policy-binding ingestion-dlq ^
    --member "serviceAccount:service-%PROJECT_NUMBER%@gcp-sa-pubsub.iam.gserviceaccount.com" ^
    --role "roles/pubsub.publisher"

call gcloud pubsub subscriptions add-iam-policy-binding worker-push-sub ^
    --member "serviceAccount:service-%PROJECT_NUMBER%@gcp-sa-pubsub.iam.gserviceaccount.com" ^
    --role "roles/pubsub.subscriber"

echo.
echo ============================================
echo DEPLOYMENT COMPLETE
echo ============================================
echo.
echo Ingestion URL: %INGESTION_URL%
echo Worker URL:   %WORKER_URL%  (private)
echo.
echo Test with:
echo curl -X POST %INGESTION_URL%/ingest -H "Content-Type: application/json" ^
  -d "{\"tenant_id\":\"acme\",\"log_id\":\"test1\",\"text\":\"hello world\"}"
echo.
pause

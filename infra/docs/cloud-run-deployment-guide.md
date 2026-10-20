# GatePass Cloud Run Deployment Guide

A step-by-step guide for deploying all 7 GatePass microservices to Google Cloud Run.

**Project ID:** `gatepass-6d009`
**Region:** `europe-west1`
**Services:** db-service, cache-service, code-service, user-profile-service, revenue-service, ai-service, notification-service

---

## 1. Prerequisites

- [Google Cloud CLI (gcloud)](https://cloud.google.com/sdk/docs/install) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- A GCP account with billing enabled

---

## 2. GCP Project Setup

1. Authenticate with Google Cloud:

```bash
gcloud auth login
```

2. Set the project:

```bash
gcloud config set project gatepass-6d009
```

3. Enable all required APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  compute.googleapis.com \
  aiplatform.googleapis.com \
  --project=gatepass-6d009
```

---

## 3. Cloud SQL (PostgreSQL)

1. Create a PostgreSQL 15 instance:

```bash
gcloud sql instances create gatepass-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=europe-west1 \
  --project=gatepass-6d009
```

2. Set the root password:

```bash
gcloud sql users set-password postgres \
  --instance=gatepass-db \
  --password=<YOUR_DB_PASSWORD> \
  --project=gatepass-6d009
```

3. Create the database:

```bash
gcloud sql databases create estate_code_db \
  --instance=gatepass-db \
  --project=gatepass-6d009
```

The db-service connects via Cloud SQL Auth Proxy sidecar, which is automatically configured using the `--add-cloudsql-instances` flag during deployment. The `DB_HOST` env var uses the Unix socket format:

```
/cloudsql/gatepass-6d009:europe-west1:gatepass-db
```

---

## 4. Redis (Upstash)

We use Upstash Redis instead of self-hosted Redis for simplicity and cost efficiency.

1. Sign up at [upstash.com](https://upstash.com)
2. Create a new Redis database (choose a region close to `europe-west1`)
3. Copy the connection URL (must use the `rediss://` TLS scheme)

The URL format is:

```
rediss://default:<PASSWORD>@<HOST>:6379
```

This goes into the `REDIS_URL` env var for cache-service.

---

## 5. GCS Bucket

Create a storage bucket for user-uploaded documents:

```bash
gcloud storage buckets create gs://gatepass-6d009-user-documents \
  --location=europe-west1 \
  --project=gatepass-6d009
```

Create a dedicated service account for db-service so only it can access the bucket:

```bash
gcloud iam service-accounts create db-service-sa \
  --display-name="db-service Cloud Run SA" \
  --project=gatepass-6d009

gcloud storage buckets add-iam-policy-binding gs://gatepass-6d009-user-documents \
  --member="serviceAccount:db-service-sa@gatepass-6d009.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:db-service-sa@gatepass-6d009.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

The db-service deploy step uses `--service-account=db-service-sa@gatepass-6d009.iam.gserviceaccount.com` to run under this SA. No other service can access the bucket.

---

## 6. Vertex AI (LLM Access for ai-service)

The ai-service uses Vertex AI (Gemini) for LLM features in production. The Cloud Run default service account needs permission to call the API:

```bash
PROJECT_NUMBER=$(gcloud projects describe gatepass-6d009 --format='value(projectNumber)')

gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

No API key or credentials file is needed. Cloud Run uses Application Default Credentials (ADC) automatically.

---

## 7. Artifact Registry

Create a Docker repository for container images:

```bash
gcloud artifacts repositories create gatepass-repo \
  --repository-format=docker \
  --location=europe-west1 \
  --description="GatePass container images" \
  --project=gatepass-6d009
```

Configure Docker authentication:

```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet
```

---

## 8. Environment Variable Files

Each service needs a YAML env file at `infra/cloudrun-env/<service>.yaml`. These files are gitignored because they contain secrets.

The format is:

```yaml
KEY: "value"
ANOTHER_KEY: "another_value"
```

### Required env vars per service

**db-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "db-service"
ENV: "production"
POSTGRES_USER: "postgres"
POSTGRES_PASSWORD: "<YOUR_DB_PASSWORD>"
POSTGRES_DB: "estate_code_db"
DB_HOST: "/cloudsql/gatepass-6d009:europe-west1:gatepass-db"
DB_PORT: "5432"
GCS_DOCUMENTS_BUCKET: "gatepass-6d009-user-documents"
GCS_SIGNED_URL_EXPIRY_SECONDS: "300"
GCS_PROFILE_PICTURE_MAX_BYTES: "5242880"
GCS_ID_CARD_MAX_BYTES: "10485760"
RATING_COMMENT_MAX_LENGTH: "1000"
ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD: "0.74"
SPATIAL_SEVERITY_HIGH_MIN: "0.8"
```

**cache-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "cache-service"
ENV: "production"
REDIS_URL: "rediss://default:<PASSWORD>@<HOST>:6379"
REDIS_HOST: "<UPSTASH_HOST>"
REDIS_PORT: "6379"
REDIS_DB: "0"
VISITOR_CODE_MAX_VALIDITY_DAYS: "14"
VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS: "7"
USER_PROFILE_CRON_URL: "https://user-profile-service-<PROJECT_NUMBER>.europe-west1.run.app/api/v1/internal/cron/daily"
REVENUE_CRON_URL: "https://revenue-service-<PROJECT_NUMBER>.europe-west1.run.app/api/v1/internal/cron/daily"
CRON_HOUR: "0"
REVENUE_CRON_HOUR: "2"
```

**code-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "code-service"
ENV: "production"
DB_SERVICE_URL: "https://db-service-<PROJECT_NUMBER>.europe-west1.run.app/"
NOTIFICATION_SERVICE_URL: "https://notification-service-<PROJECT_NUMBER>.europe-west1.run.app/"
CACHE_SERVICE_URL: "https://cache-service-<PROJECT_NUMBER>.europe-west1.run.app/"
REVENUE_SERVICE_URL: "https://revenue-service-<PROJECT_NUMBER>.europe-west1.run.app/"
AI_SERVICE_URL: "https://ai-service-<PROJECT_NUMBER>.europe-west1.run.app/"
RESIDENT_CODE_EXPIRY_DAYS: "30"
```

**user-profile-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "user-profile-service"
ENV: "production"
DB_SERVICE_URL: "https://db-service-<PROJECT_NUMBER>.europe-west1.run.app/"
NOTIFICATION_SERVICE_URL: "https://notification-service-<PROJECT_NUMBER>.europe-west1.run.app/"
REVENUE_SERVICE_URL: "https://revenue-service-<PROJECT_NUMBER>.europe-west1.run.app/"
CACHE_SERVICE_URL: "https://cache-service-<PROJECT_NUMBER>.europe-west1.run.app/"
LOGIN_EXPIRE_MINUTES: "60"
SESSION_EXPIRE_DAYS: "30"
TOS_VERSION: "1.0.0"
TOTP_ENCRYPTION_KEY: "<YOUR_TOTP_KEY>"
TWO_FA_FAMILIAR_IP_DAYS: "30"
TWO_FA_FORCE_REAUTH_DAYS: "60"
EDIT_REQUEST_REMIND_COOLDOWN_HOURS: "24"
SCHEDULE_CLOSE_MAX_DAYS: "30"
NOTIFICATION_MAX_AGE_DAYS: "90"
NOTIFICATION_PURGE_MIN_AGE_DAYS: "90"
GCS_PROFILE_PICTURE_MAX_BYTES: "5242880"
GCS_ID_CARD_MAX_BYTES: "10485760"
```

**revenue-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "revenue-service"
ENV: "production"
DB_SERVICE_URL: "https://db-service-<PROJECT_NUMBER>.europe-west1.run.app/"
NOTIFICATION_SERVICE_URL: "https://notification-service-<PROJECT_NUMBER>.europe-west1.run.app/"
PAYSTACK_SECRET_KEY: "<YOUR_PAYSTACK_SECRET_KEY>"
PAYSTACK_PUBLIC_KEY: "<YOUR_PAYSTACK_PUBLIC_KEY>"
PAYSTACK_CALLBACK_URL: "https://app.gatepassng.com/payment/callback"
PAYSTACK_BASE_URL: "https://api.paystack.co"
PAYSTACK_TIMEOUT_SECONDS: "30.0"
RENEWAL_GRACE_PERIOD_DAYS: "7"
PRE_EXPIRY_WARNING_DAYS: "1"
CHECKOUT_TOKEN_EXPIRY_SECONDS: "7200"
REVENUE_TRANSIENT_RETRY_ATTEMPTS: "3"
REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS: "0.2"
ESTATE_TYPE_HOUSING_MULTIPLIER: "1.0"
ESTATE_TYPE_CORPORATE_MULTIPLIER: "3.0"
```

**ai-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "ai-service"
ENV: "production"
DB_SERVICE_URL: "https://db-service-<PROJECT_NUMBER>.europe-west1.run.app/"
REVENUE_SERVICE_URL: "https://revenue-service-<PROJECT_NUMBER>.europe-west1.run.app/"
USER_PROFILE_SERVICE_URL: "https://user-profile-service-<PROJECT_NUMBER>.europe-west1.run.app/"
CODE_SERVICE_URL: "https://code-service-<PROJECT_NUMBER>.europe-west1.run.app/"
GCP_PROJECT_ID: "gatepass-6d009"
GCP_VERTEX_LOCATION: "global"
GCP_LLM_CHAT_MODEL: "google/gemini-2.5-flash"
OPENAI_API_KEY: "<YOUR_OPENAI_API_KEY>"
OPENAI_CHAT_MODEL: "gpt-4o-mini"
OPENAI_BASE_URL: "https://api.openai.com"
RATING_COMMENT_MAX_LENGTH: "1000"
ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD: "0.74"
SPATIAL_SEVERITY_HIGH_MIN: "0.8"
SPATIAL_EXPECTED_REFERENCE_CAP: "10"
SPATIAL_MIN_MATCHED_TO_SCORE: "5"
SPATIAL_HISTORY_CONFIDENCE_FLOOR: "0.0"
SPATIAL_SCOPE_HISTORY_LIMIT: "40"
SPATIAL_ANOMALY_PAYLOAD_DEBUG: "false"
SPATIAL_KMEANS_MAX_CLUSTERS: "8"
SPATIAL_KMEANS_RANDOM_STATE: "42"
SPATIAL_KMEANS_HIST_DISTANCE_PERCENTILE: "95.0"
SPATIAL_DBSCAN_FALLBACK_EPS: "0.75"
SPATIAL_DBSCAN_MIN_SAMPLES_FLOOR: "2"
SPATIAL_DBSCAN_MIN_SAMPLES_CAP: "5"
SPATIAL_DBSCAN_INCLUSTER_BASELINE: "0.05"
SPATIAL_DBSCAN_NOISE_BLEND_BASE: "0.15"
SPATIAL_DBSCAN_NOISE_BLEND_SCALE: "0.85"
SPATIAL_LOF_MAX_NEIGHBORS: "20"
SPATIAL_LOF_CONTAMINATION: "auto"
SPATIAL_LOF_INLIER_BASELINE: "0.05"
SPATIAL_LOF_INLIER_MAX: "0.5"
SPATIAL_LOF_INLIER_UPLIFT_SCALE: "0.45"
TEMPORAL_ANOMALY_SCORE_THRESHOLD: "0.5"
TEMPORAL_SUBSEQUENCE_WINDOW_DAYS: "7"
TEMPORAL_MIN_HISTORY_WINDOW_MULTIPLE: "3"
```

**notification-service.yaml:**

```yaml
SECRET_KEY: "<YOUR_SECRET_KEY>"
INTERNAL_API_KEY: "<YOUR_INTERNAL_API_KEY>"
FRONTEND_BASE_URL: "https://app.gatepassng.com"
SERVICE_NAME: "notification-service"
ENV: "production"
DB_SERVICE_URL: "https://db-service-<PROJECT_NUMBER>.europe-west1.run.app/"
FCM_CREDENTIALS_JSON: '<YOUR_FCM_SERVICE_ACCOUNT_JSON>'
MAIL_USERNAME: "<YOUR_MAIL_USERNAME>"
MAIL_PASSWORD: "<YOUR_MAIL_PASSWORD>"
MAIL_FROM: "<YOUR_MAIL_FROM>"
MAIL_FROM_NAME: "GatePass"
MAIL_SERVER: "smtp.zoho.com"
MAIL_PORT: "465"
MAIL_SSL_TLS: "true"
MAIL_STARTTLS: "false"
MAIL_DEV_MODE: "false"
FEEDBACK_RECIPIENT_EMAIL: "info@gatepassng.com"
NOTIFICATION_MAX_AGE_DAYS: "90"
NOTIFICATION_PURGE_MIN_AGE_DAYS: "90"
```

---

## 9. Secret Manager

Upload each env file as a secret so Cloud Build can access them during deployment.

1. Upload all secrets:

```bash
gcloud secrets create db-service-env --data-file=infra/cloudrun-env/db-service.yaml --project=gatepass-6d009
gcloud secrets create cache-service-env --data-file=infra/cloudrun-env/cache-service.yaml --project=gatepass-6d009
gcloud secrets create code-service-env --data-file=infra/cloudrun-env/code-service.yaml --project=gatepass-6d009
gcloud secrets create user-profile-service-env --data-file=infra/cloudrun-env/user-profile-service.yaml --project=gatepass-6d009
gcloud secrets create revenue-service-env --data-file=infra/cloudrun-env/revenue-service.yaml --project=gatepass-6d009
gcloud secrets create ai-service-env --data-file=infra/cloudrun-env/ai-service.yaml --project=gatepass-6d009
gcloud secrets create notification-service-env --data-file=infra/cloudrun-env/notification-service.yaml --project=gatepass-6d009
```

2. To update a secret later:

```bash
gcloud secrets versions add <service>-env \
  --data-file=infra/cloudrun-env/<service>.yaml \
  --project=gatepass-6d009
```

---

## 10. First Deploy (Manual)

### 10a. Build and push images

Build all images from the repo root:

```bash
REGISTRY="europe-west1-docker.pkg.dev/gatepass-6d009/gatepass-repo"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

docker build -f services/db-service/Dockerfile --platform linux/amd64 -t $REGISTRY/db-service:$TIMESTAMP .
docker build -f services/cache_service/Dockerfile --platform linux/amd64 -t $REGISTRY/cache-service:$TIMESTAMP .
docker build -f services/code_service/Dockerfile --platform linux/amd64 -t $REGISTRY/code-service:$TIMESTAMP .
docker build -f services/user_profile_service/Dockerfile --platform linux/amd64 -t $REGISTRY/user-profile-service:$TIMESTAMP .
docker build -f services/revenue_service/Dockerfile --platform linux/amd64 -t $REGISTRY/revenue-service:$TIMESTAMP .
docker build -f services/ai_service/Dockerfile --platform linux/amd64 -t $REGISTRY/ai-service:$TIMESTAMP .
docker build -f services/notification_service/Dockerfile --platform linux/amd64 -t $REGISTRY/notification-service:$TIMESTAMP .
```

Push all images:

```bash
docker push $REGISTRY/db-service:$TIMESTAMP
docker push $REGISTRY/cache-service:$TIMESTAMP
docker push $REGISTRY/code-service:$TIMESTAMP
docker push $REGISTRY/user-profile-service:$TIMESTAMP
docker push $REGISTRY/revenue-service:$TIMESTAMP
docker push $REGISTRY/ai-service:$TIMESTAMP
docker push $REGISTRY/notification-service:$TIMESTAMP
```

### 10b. Deploy each service

```bash
gcloud run deploy db-service \
  --image=$REGISTRY/db-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/db-service.yaml \
  --min-instances=1 --max-instances=5 \
  --memory=512Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --add-cloudsql-instances=gatepass-6d009:europe-west1:gatepass-db \
  --project=gatepass-6d009

gcloud run deploy cache-service \
  --image=$REGISTRY/cache-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/cache-service.yaml \
  --min-instances=1 --max-instances=3 \
  --memory=256Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009

gcloud run deploy code-service \
  --image=$REGISTRY/code-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/code-service.yaml \
  --min-instances=1 --max-instances=10 \
  --memory=512Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009

gcloud run deploy user-profile-service \
  --image=$REGISTRY/user-profile-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/user-profile-service.yaml \
  --min-instances=1 --max-instances=10 \
  --memory=512Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009

gcloud run deploy revenue-service \
  --image=$REGISTRY/revenue-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/revenue-service.yaml \
  --min-instances=0 --max-instances=5 \
  --memory=512Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009

gcloud run deploy ai-service \
  --image=$REGISTRY/ai-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/ai-service.yaml \
  --min-instances=1 --max-instances=5 \
  --memory=512Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009

gcloud run deploy notification-service \
  --image=$REGISTRY/notification-service:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/notification-service.yaml \
  --min-instances=0 --max-instances=3 \
  --memory=256Mi --cpu=1 --port=8080 \
  --allow-unauthenticated \
  --project=gatepass-6d009
```

After the first deploy, note each service's URL (printed in the output). You will need these to fill in the inter-service URLs (e.g., `DB_SERVICE_URL`, `CACHE_SERVICE_URL`) in the env files.

---

## 11. Load Balancer Setup

### 11a. Reserve a static IP

```bash
gcloud compute addresses create gatepass-lb-ip --global --project=gatepass-6d009
```

Note the IP address from the output. You will need it for DNS.

### 11b. Create serverless NEGs (one per public service)

```bash
gcloud compute network-endpoint-groups create code-service-neg \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=code-service \
  --project=gatepass-6d009

gcloud compute network-endpoint-groups create user-profile-service-neg \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=user-profile-service \
  --project=gatepass-6d009

gcloud compute network-endpoint-groups create ai-service-neg \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=ai-service \
  --project=gatepass-6d009

gcloud compute network-endpoint-groups create revenue-service-neg \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=revenue-service \
  --project=gatepass-6d009
```

### 11c. Create backend services and attach NEGs

```bash
for svc in code-service user-profile-service ai-service revenue-service; do
  gcloud compute backend-services create ${svc}-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED \
    --protocol=HTTP \
    --project=gatepass-6d009

  gcloud compute backend-services add-backend ${svc}-backend \
    --global \
    --network-endpoint-group=${svc}-neg \
    --network-endpoint-group-region=europe-west1 \
    --project=gatepass-6d009
done
```

### 11d. Create URL map (path-based routing)

```bash
gcloud compute url-maps create gatepass-api-urlmap \
  --default-service=code-service-backend \
  --project=gatepass-6d009

gcloud compute url-maps add-path-matcher gatepass-api-urlmap \
  --path-matcher-name=api-routes \
  --default-service=code-service-backend \
  --path-rules="/code/*=code-service-backend,/user/*=user-profile-service-backend,/ai/*=ai-service-backend,/revenue/*=revenue-service-backend" \
  --project=gatepass-6d009
```

### 11e. Create SSL certificate

```bash
gcloud compute ssl-certificates create gatepass-api-cert \
  --domains=api.gatepassng.com \
  --global \
  --project=gatepass-6d009
```

### 11f. Create HTTPS proxy and forwarding rule

```bash
gcloud compute target-https-proxies create gatepass-api-https-proxy \
  --ssl-certificates=gatepass-api-cert \
  --url-map=gatepass-api-urlmap \
  --project=gatepass-6d009

gcloud compute forwarding-rules create gatepass-api-fw-rule \
  --global \
  --target-https-proxy=gatepass-api-https-proxy \
  --address=gatepass-lb-ip \
  --ports=443 \
  --project=gatepass-6d009
```

### 11g. DNS

Add an A record in your DNS provider:

| Type | Name | Value |
|------|------|-------|
| A | api | (your static IP from step 10a) |

Check SSL certificate status (takes 10-30 minutes to activate):

```bash
gcloud compute ssl-certificates describe gatepass-api-cert \
  --global --project=gatepass-6d009 \
  --format="get(managed.status)"
```

---

## 12. Ingress Lockdown

Lock down public services so they are only reachable through the load balancer:

```bash
gcloud run services update code-service --ingress=internal-and-cloud-load-balancing --region=europe-west1 --project=gatepass-6d009
gcloud run services update user-profile-service --ingress=internal-and-cloud-load-balancing --region=europe-west1 --project=gatepass-6d009
gcloud run services update ai-service --ingress=internal-and-cloud-load-balancing --region=europe-west1 --project=gatepass-6d009
gcloud run services update revenue-service --ingress=internal-and-cloud-load-balancing --region=europe-west1 --project=gatepass-6d009
```

Lock down internal services so they are only reachable by other Cloud Run services:

```bash
gcloud run services update db-service --ingress=internal --region=europe-west1 --project=gatepass-6d009
gcloud run services update cache-service --ingress=internal --region=europe-west1 --project=gatepass-6d009
gcloud run services update notification-service --ingress=internal --region=europe-west1 --project=gatepass-6d009
```

---

## 13. Cloud Build (CI/CD)

### 13a. Enable the API

```bash
gcloud services enable cloudbuild.googleapis.com --project=gatepass-6d009
```

### 13b. Connect GitHub repo

1. Go to: https://console.cloud.google.com/cloud-build/triggers?project=gatepass-6d009
2. Click "Connect Repository"
3. Select "GitHub (Cloud Build GitHub App)"
4. Authenticate and select the repo

### 13c. Grant Cloud Build permissions

```bash
PROJECT_NUMBER=$(gcloud projects describe gatepass-6d009 --format='value(projectNumber)')

gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 13d. Create the trigger

Create a trigger via the console:

1. Go to: https://console.cloud.google.com/cloud-build/triggers?project=gatepass-6d009
2. Click "Create Trigger"
3. Set name: `deploy-on-push-to-main`
4. Event: Push to a branch
5. Source: your connected repo
6. Branch: `^main$`
7. Configuration: Cloud Build configuration file, path: `cloudbuild.yaml`
8. Click "Create"

### 13e. How it works

The `cloudbuild.yaml` in the repo root runs the following pipeline on every push to main:

1. **Fetch secrets**: Pulls env files from Secret Manager into `infra/cloudrun-env/`
2. **Check env**: Validates env vars against each service's config.py
3. **Build**: Builds all 7 Docker images in parallel
4. **Push**: Pushes all images to Artifact Registry in parallel
5. **Deploy**: Deploys all 7 services to Cloud Run in parallel

---

## 14. Cloud Armor (Pending)

Cloud Armor requires a quota increase for `SECURITY_POLICIES` (new accounts start at 0). Once approved:

1. Create a security policy:

```bash
gcloud compute security-policies create gatepass-waf \
  --description="WAF + rate-limiting for GatePass API" \
  --project=gatepass-6d009
```

2. Add OWASP rules:

```bash
gcloud compute security-policies rules create 1000 \
  --security-policy=gatepass-waf \
  --expression="evaluatePreconfiguredExpr('xss-v33-stable')" \
  --action=deny-403 \
  --project=gatepass-6d009

gcloud compute security-policies rules create 1001 \
  --security-policy=gatepass-waf \
  --expression="evaluatePreconfiguredExpr('sqli-v33-stable')" \
  --action=deny-403 \
  --project=gatepass-6d009
```

3. Add rate limiting:

```bash
gcloud compute security-policies rules create 2000 \
  --security-policy=gatepass-waf \
  --src-ip-ranges="*" \
  --action=throttle \
  --rate-limit-threshold-count=100 \
  --rate-limit-threshold-interval-sec=60 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --project=gatepass-6d009
```

4. Attach to all backend services:

```bash
for svc in code-service-backend user-profile-service-backend ai-service-backend revenue-service-backend; do
  gcloud compute backend-services update $svc \
    --security-policy=gatepass-waf \
    --global \
    --project=gatepass-6d009
done
```

---

## 15. Updating Environment Variables

1. Edit the local YAML file:

```bash
vim infra/cloudrun-env/code-service.yaml
```

2. Push the new version to Secret Manager:

```bash
gcloud secrets versions add code-service-env \
  --data-file=infra/cloudrun-env/code-service.yaml \
  --project=gatepass-6d009
```

3. Trigger a deploy by either pushing a commit to main, or manually running the trigger from the Cloud Build console.

---

## 16. Env Checker Script

Run locally before pushing to validate env files:

```bash
bash infra/check-env.sh
```

This compares each `infra/cloudrun-env/<service>.yaml` against the service's `config.py` and checks for:

- Missing env vars (expected by code but not in YAML)
- Extra env vars (in YAML but not in code)
- Empty values
- Inconsistent shared keys (SECRET_KEY, INTERNAL_API_KEY)
- Inter-service URLs pointing to the correct domain

The env checker also runs automatically as the first step in every Cloud Build deploy.

---

## 17. Useful Commands

Check service status:

```bash
gcloud run services list --region=europe-west1 --project=gatepass-6d009
```

View logs for a service:

```bash
gcloud run services logs read code-service --region=europe-west1 --project=gatepass-6d009 --limit=50
```

Manually deploy a single service:

```bash
bash infra/deploy-cloudrun.sh code-service
```

Check Cloud Build history:

```bash
gcloud builds list --project=gatepass-6d009 --limit=5
```

Rollback to a previous revision:

```bash
gcloud run services update-traffic code-service \
  --to-revisions=<REVISION_NAME>=100 \
  --region=europe-west1 \
  --project=gatepass-6d009
```

List revisions for a service:

```bash
gcloud run revisions list --service=code-service --region=europe-west1 --project=gatepass-6d009
```

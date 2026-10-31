# GatePass Monolith Consolidation Guide

## Why consolidate?

With zero active users, running 7 separate Cloud Run services is wasteful. The current setup keeps 5 services always-on (`min-instances=1`) and 2 that can scale to zero. Each warm instance incurs CPU and memory charges even when idle.

By packing all 7 services into a single Cloud Run container, we drop from 5+ running instances to 1. The services still run as independent processes, talking over `localhost` instead of Cloud Run internal URLs. No application code changes are required.

This is a **temporary cost optimization**. When traffic justifies it, we split back to the distributed setup by redeploying the original images and restoring the load balancer.

---

## Architecture: before and after

### Before (distributed)

```
Internet
  |
  v
Google Cloud Load Balancer (api.gatepassng.com)
  |-- /code/*     --> code-service       (Cloud Run, min=1)
  |-- /user/*     --> user-profile       (Cloud Run, min=1)
  |-- /ai/*       --> ai-service         (Cloud Run, min=1)
  |-- /revenue/*  --> revenue-service    (Cloud Run, min=0)
  |
  (internal only, VPC)
  |-- db-service           (Cloud Run, min=1)
  |-- cache-service        (Cloud Run, min=1)
  |-- notification-service (Cloud Run, min=0)
```

### After (consolidated)

```
Internet
  |
  v
Cloud Run (single service: gatepass-monolith, min=1)
  |
  nginx (:8080 = $PORT)
  |-- /code/*     --> localhost:9033  (code-service)
  |-- /user/*     --> localhost:9034  (user-profile-service)
  |-- /ai/*       --> localhost:9036  (ai-service)
  |-- /revenue/*  --> localhost:9037  (revenue-service)
  |-- /*          --> 404 (everything else blocked)
  |
  (internal only, localhost)
  |-- localhost:9032  db-service
  |-- localhost:9031  cache-service
  |-- localhost:9035  notification-service
```

Internal services (db, cache, notification) are **not routed by nginx** and are only reachable via `localhost` inside the container. This preserves the same isolation as the current `ingress=internal` setup.

---

## What changes

| Aspect             | Distributed                       | Consolidated                             |
| ------------------ | --------------------------------- | ---------------------------------------- |
| Cloud Run services | 7                                 | 1 (`gatepass-monolith`)                  |
| Process manager    | N/A                               | supervisord (7 uvicorn + 1 nginx)        |
| Inter-service URLs | Cloud Run internal URLs           | `http://localhost:<port>/`               |
| Public routing     | Google Cloud LB (path-based)      | nginx inside container                   |
| Cloud Armor / WAF  | Via LB (pending quota)            | Not available (use `slowapi` or similar) |
| Secret Manager     | 7 secrets (`<service>-env`)       | 1 secret (`gatepass-monolith-env`)       |
| Cloud Build        | Build 7 images, deploy 7 services | Build 1 image, deploy 1 service          |
| Memory             | ~256-512Mi per service            | ~2GB total (single instance)             |
| CPU                | 1 vCPU per service                | 2 vCPUs (single instance)                |
| CPU throttling     | Default (throttled when idle)     | Disabled (`--no-cpu-throttling`)         |
| Cold start         | ~3-5s per service                 | ~10-15s (all 7 boot)                     |
| min-instances cost | 5 always-on instances             | 1 always-on instance                     |

---

## What does NOT change

- **Application code**: Zero changes. Each service's `app/` directory is untouched.
- **Shared libraries**: `gatepass_auth`, `gatepass_rbac`, etc. remain as-is.
- **Database**: Same Cloud SQL instance, same connection string.
- **Redis**: Same Upstash Redis URL.
- **GCS**: Same bucket, same signed URLs.
- **Vertex AI**: Same ADC auth via service account.
- **Docker Compose (local dev)**: Unchanged. Local dev still runs 7 separate containers.
- **Individual Dockerfiles**: Kept. They are still used for local dev and for splitting back.
- **DB migrations**: Still run via Alembic. The monolith Dockerfile includes the db-service code.

---

## New files

All new files live under `infra/monolith/`. No existing files are modified or deleted.

### `infra/monolith/Dockerfile`

Single multi-stage Dockerfile that installs all 7 services, nginx, and supervisord.

Key points:

- Based on `python:3.11-slim` (same as individual services)
- Installs each service's dependencies via Poetry
- Installs nginx and supervisord via apt
- Copies shared libraries once (not 7 times)
- Uses the db-service SA for Cloud SQL Auth Proxy and GCS access
- Exposes port 8080 (Cloud Run's `$PORT`)

### `infra/monolith/nginx.conf`

Routes external traffic to the 4 public services. All other paths return 404.

```nginx
upstream code_service     { server 127.0.0.1:9033; }
upstream user_service     { server 127.0.0.1:9034; }
upstream ai_service       { server 127.0.0.1:9036; }
upstream revenue_service  { server 127.0.0.1:9037; }

server {
    listen 8080;

    location /code/    { proxy_pass http://code_service; }
    location /user/    { proxy_pass http://user_service; }
    location /ai/      { proxy_pass http://ai_service; }
    location /revenue/ { proxy_pass http://revenue_service; }

    # Health check for Cloud Run
    location = /healthz {
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    location / { return 404; }
}
```

### `infra/monolith/supervisord.conf`

Manages all 8 processes (7 uvicorn + 1 nginx). If any process crashes, supervisord restarts it. If nginx (the entrypoint) dies, the container exits.

### `infra/monolith/entrypoint.sh`

Starts supervisord as PID 1. Handles SIGTERM gracefully so Cloud Run can shut down cleanly.

---

## Environment variables

### Merging 7 env files into 1

In the distributed setup, each service has its own Secret Manager secret (`<service>-env`). In the consolidated setup, all env vars go into one secret: `gatepass-monolith-env`.

Key changes:

- **Inter-service URLs** become localhost:
  ```yaml
  DB_SERVICE_URL: "http://localhost:9032/"
  NOTIFICATION_SERVICE_URL: "http://localhost:9035/"
  CACHE_SERVICE_URL: "http://localhost:9031/"
  REVENUE_SERVICE_URL: "http://localhost:9037/"
  AI_SERVICE_URL: "http://localhost:9036/"
  USER_PROFILE_SERVICE_URL: "http://localhost:9034/"
  CODE_SERVICE_URL: "http://localhost:9033/"
  ```
- **Cron URLs** also become localhost:
  ```yaml
  USER_PROFILE_CRON_URL: "http://localhost:9034/api/v1/internal/cron/daily"
  REVENUE_CRON_URL: "http://localhost:9037/api/v1/internal/cron/daily"
  ```
- **Shared vars** (`SECRET_KEY`, `INTERNAL_API_KEY`, `APP_ENV`, etc.) appear once.
- **Service-specific vars** are all present in the single file. There are no naming collisions because each service reads only the vars it cares about (via its own `config.py`).
- **`DB_HOST`** still uses the Cloud SQL socket path: `/cloudsql/gatepass-6d009:europe-west1:gatepass-db`

### Collision check

Review each service's `config.py` for vars with the same name but different meanings. Currently there are **no collisions** — shared vars (`SECRET_KEY`, `INTERNAL_API_KEY`, `FRONTEND_BASE_URL`, `APP_ENV`, `ENV`) are intentionally identical across services.

---

## Cloud Build changes

Replace the current `cloudbuild.yaml` pipeline (or create `cloudbuild-monolith.yaml` alongside it) with a simplified version:

1. Fetch env from Secret Manager (`gatepass-monolith-env`)
2. Build 1 Docker image
3. Push 1 image
4. Run Alembic migrations (same as before, using the monolith image)
5. Deploy 1 Cloud Run service

---

## Deployment steps

### 1. Create the monolith env file

Merge all 7 env files into `infra/cloudrun-env/gatepass-monolith.yaml`, replacing inter-service URLs with localhost equivalents.

### 2. Grant Vertex AI access to the monolith SA

The distributed setup uses the default Compute Engine SA for ai-service (which has `roles/aiplatform.user`). The monolith runs under `db-service-sa`, so it needs the same role:

```bash
gcloud projects add-iam-policy-binding gatepass-6d009 \
  --member="serviceAccount:db-service-sa@gatepass-6d009.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

This is a one-time setup step.

### 3. Upload to Secret Manager

```bash
gcloud secrets create gatepass-monolith-env \
  --data-file=infra/cloudrun-env/gatepass-monolith.yaml \
  --project=gatepass-6d009
```

### 4. Build and push the image

```bash
REGISTRY="europe-west1-docker.pkg.dev/gatepass-6d009/gatepass-repo"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

docker build -f infra/monolith/Dockerfile \
  --platform linux/amd64 \
  -t $REGISTRY/gatepass-monolith:$TIMESTAMP .

docker push $REGISTRY/gatepass-monolith:$TIMESTAMP
```

### 5. Deploy to Cloud Run

```bash
gcloud run deploy gatepass-monolith \
  --image=$REGISTRY/gatepass-monolith:$TIMESTAMP \
  --region=europe-west1 \
  --env-vars-file=infra/cloudrun-env/gatepass-monolith.yaml \
  --min-instances=1 \
  --max-instances=5 \
  --memory=2Gi \
  --cpu=2 \
  --port=8080 \
  --timeout=300 \
  --no-cpu-throttling \
  --allow-unauthenticated \
  --add-cloudsql-instances=gatepass-6d009:europe-west1:gatepass-db \
  --service-account=db-service-sa@gatepass-6d009.iam.gserviceaccount.com \
  --project=gatepass-6d009
```

> **Important:** `--no-cpu-throttling` is required. Without it, Cloud Run throttles CPU after nginx passes the startup probe, starving the 7 uvicorn processes before they finish booting (results in 502s).

### 6. Route the Load Balancer to the monolith

The existing Load Balancer (`api.gatepassng.com`) is reused. Replace the 4 per-service backends with a single monolith backend. DNS, SSL, and the static IP stay unchanged.

```bash
# Create a serverless NEG for the monolith
gcloud compute network-endpoint-groups create gatepass-monolith-neg \
  --region=europe-west1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=gatepass-monolith \
  --project=gatepass-6d009

# Create a backend service and attach the NEG
gcloud compute backend-services create gatepass-monolith-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --project=gatepass-6d009

gcloud compute backend-services add-backend gatepass-monolith-backend \
  --global \
  --network-endpoint-group=gatepass-monolith-neg \
  --network-endpoint-group-region=europe-west1 \
  --project=gatepass-6d009

# Export the URL map, remove old path rules, and reimport
gcloud compute url-maps export gatepass-api-urlmap \
  --global --project=gatepass-6d009 \
  --destination=/tmp/urlmap.yaml

# Edit /tmp/urlmap.yaml — remove all pathRules entries and set the
# path matcher's defaultService to the monolith backend:
#
#   pathMatchers:
#   - defaultService: .../gatepass-monolith-backend
#     name: api-routes
#
# Then reimport:
gcloud compute url-maps import gatepass-api-urlmap \
  --global --project=gatepass-6d009 \
  --source=/tmp/urlmap.yaml
```

### 7. Lock down ingress

Restrict the monolith so it's only reachable through the Load Balancer (blocks direct access via the `.run.app` URL):

```bash
gcloud run services update gatepass-monolith \
  --ingress=internal-and-cloud-load-balancing \
  --region=europe-west1 \
  --project=gatepass-6d009
```

### 8. Set up Google Cloud Scheduler (cron jobs)

In the distributed setup, the cache-service ran two `asyncio` sleep loops to trigger daily cron endpoints. In production, these are replaced by Google Cloud Scheduler — a managed cron service that hits the endpoints through the Load Balancer.

The cache-service's in-process scheduler is automatically skipped when `APP_ENV=production`.

```bash
# User profile daily cron — midnight UTC
gcloud scheduler jobs create http user-profile-daily-cron \
  --location=europe-west1 \
  --schedule="0 0 * * *" \
  --uri="https://api.gatepassng.com/user/api/v1/internal/cron/daily" \
  --http-method=POST \
  --headers="X-Internal-Key=<YOUR_INTERNAL_API_KEY>" \
  --attempt-deadline=300s \
  --project=gatepass-6d009

# Revenue daily expiry — 2am UTC
gcloud scheduler jobs create http revenue-daily-expiry \
  --location=europe-west1 \
  --schedule="0 2 * * *" \
  --uri="https://api.gatepassng.com/revenue/api/v1/internal/cron/daily" \
  --http-method=POST \
  --headers="X-Internal-Key=<YOUR_INTERNAL_API_KEY>" \
  --attempt-deadline=300s \
  --project=gatepass-6d009
```

To test:

```bash
gcloud scheduler jobs run user-profile-daily-cron --location=europe-west1 --project=gatepass-6d009
gcloud scheduler jobs run revenue-daily-expiry --location=europe-west1 --project=gatepass-6d009
```

To update the schedule or API key later:

```bash
gcloud scheduler jobs update http <JOB_NAME> \
  --schedule="0 1 * * *" \
  --headers="X-Internal-Key=NEW_KEY" \
  --location=europe-west1 --project=gatepass-6d009
```

### 9. Delete old services

Once the monolith is verified:

```bash
for svc in db-service cache-service code-service user-profile-service revenue-service ai-service notification-service; do
  gcloud run services delete $svc --region=europe-west1 --project=gatepass-6d009 --quiet
done
```

> **Note:** Reverting to distributed services later means redeploying each service from scratch using the original `cloudbuild.yaml` and Dockerfiles (which are kept in the repo). See the [Reverting](#reverting-to-distributed-services) section.

---

## Reverting to distributed services

When traffic grows and you need to split back, follow these steps. You can split gradually (one service at a time) or all at once.

### Full revert (all at once)

1. **Re-enable old services:**

   ```bash
   # Restore original min-instances for each service
   gcloud run services update db-service --min-instances=1 --max-instances=5 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update cache-service --min-instances=1 --max-instances=3 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update code-service --min-instances=1 --max-instances=10 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update user-profile-service --min-instances=1 --max-instances=10 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update revenue-service --min-instances=0 --max-instances=5 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update ai-service --min-instances=1 --max-instances=5 --region=europe-west1 --project=gatepass-6d009
   gcloud run services update notification-service --min-instances=0 --max-instances=3 --region=europe-west1 --project=gatepass-6d009
   ```

2. **Update env vars** in each service's Secret Manager secret — restore the Cloud Run internal URLs (replace `localhost` with `https://<service>-<hash>.europe-west1.run.app/`).

3. **Deploy latest code** to each service using the original `cloudbuild.yaml`.

4. **Restore the LB URL map** to route per-service paths to the original backends:

   ```bash
   gcloud compute url-maps add-path-matcher gatepass-api-urlmap \
     --path-matcher-name=api-routes \
     --default-service=code-service-backend \
     --path-rules="/code/*=code-service-backend,/user/*=user-profile-service-backend,/ai/*=ai-service-backend,/revenue/*=revenue-service-backend" \
     --project=gatepass-6d009
   ```

5. **Lock down ingress** on public services (`internal-and-cloud-load-balancing`) and internal services (`internal`), per [Deployment Guide section 12](cloud-run-deployment-guide.md#12-ingress-lockdown).

6. **Scale down the monolith:**
   ```bash
   gcloud run services update gatepass-monolith \
     --min-instances=0 --max-instances=1 \
     --region=europe-west1 --project=gatepass-6d009
   ```

### Gradual revert (one service at a time)

You can peel off individual services while the monolith still handles the rest. For example, to split out `ai-service` first (likely candidate due to heavier memory/CPU needs):

1. Deploy `ai-service` as its own Cloud Run service.
2. In the monolith's env file, change `AI_SERVICE_URL` from `http://localhost:9036/` to the new Cloud Run URL.
3. In `supervisord.conf`, remove the ai-service process (or stop it).
4. Redeploy the monolith.
5. Update the LB or nginx to route `/ai/*` to the standalone service.

Repeat for each service. The last service peeled off is the monolith itself.

---

## Risks and mitigations

| Risk                                                      | Mitigation                                                                                                                                                  |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Single point of failure (1 container = all services down) | Cloud Run auto-restarts crashed containers. supervisord restarts individual processes. With 0 users this is acceptable.                                     |
| Slower cold start (~10-15s vs ~3-5s)                      | Keep `min-instances=1` so cold starts are rare.                                                                                                             |
| No Cloud Armor (WAF/rate-limiting)                        | Add `slowapi` middleware if needed, or keep the LB in front (Option B).                                                                                     |
| Higher memory per instance                                | Set `--memory=2Gi`. Still cheaper than 5+ separate instances.                                                                                               |
| CPU throttling kills uvicorn processes                    | Deploy with `--no-cpu-throttling`. Nginx passes the startup probe instantly; without always-on CPU, the 7 uvicorn processes never finish booting.           |
| Logging all mixed together                                | Each service already logs its `APP_NAME`. Use Cloud Logging filters: `jsonPayload.app_name="code-service"`.                                                 |
| Dependency conflicts between services                     | All services already share the same Python 3.11 base and compatible deps. The AI service's ML stack (scikit-learn, numpy) adds image size but no conflicts. |

---

## Related docs

- [Infrastructure Overview](infrastructure-overview.md) — describes the distributed architecture this consolidation replaces
- [Cloud Run Deployment Guide](cloud-run-deployment-guide.md) — step-by-step setup for the distributed deployment (used for reverting)

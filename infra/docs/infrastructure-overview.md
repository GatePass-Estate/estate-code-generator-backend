# GatePass Backend Infrastructure Overview

## Hosting

All 7 microservices run on **Google Cloud Run** in the `europe-west1` (Belgium) region. Belgium was chosen as the closest Google Cloud region to Nigeria, providing the lowest latency for our primary user base.

Cloud Run automatically scales each service up or down based on traffic. Five core services (db, cache, code, user-profile, AI) always keep at least one instance running. Two supporting services (revenue, notifications) can scale to zero when not in use to save costs.

## Database

We use **Google Cloud SQL** (PostgreSQL 15) as the managed database. The db-service connects through Google's Cloud SQL Auth Proxy sidecar, so no database credentials are exposed over the network.

## Caching

We use **Upstash Redis** (managed, external) instead of self-hosting Redis. It charges per request rather than a flat monthly rate, keeping costs low during early stages. No code changes were needed, just a connection URL swap.

## File Storage

User-uploaded files (profile pictures, ID cards) are stored in **Google Cloud Storage** and served via signed URLs.

## API Gateway

All external traffic goes through a **Google Cloud External Load Balancer** at `api.gatepassng.com` with automatic SSL. Requests are routed by URL path:

- `/code/*` -> code-service
- `/user/*` -> user-profile-service
- `/ai/*` -> ai-service
- `/revenue/*` -> revenue-service

Only these four services are internet-facing. The other three (db, cache, notification) are internal only.

**Cloud Armor** (WAF + rate limiting) will be added once the account quota is approved.

## AI / LLM

The ai-service uses **Google Vertex AI** (Gemini) in production for LLM features. Authentication is handled automatically through Cloud Run's default service account (no API key or credentials file needed). The service account has the `roles/aiplatform.user` IAM role.

## Secrets Management

All sensitive config is stored in **Google Cloud Secret Manager**. Nothing is committed to git. Each service has its own secret named `<service>-env` containing a YAML env file.

## CI/CD

**Google Cloud Build** automatically builds and deploys all services when code is pushed to `main`. The pipeline:

1. Fetches env files from Secret Manager
2. Validates env vars against each service's `config.py`
3. Builds all 7 Docker images in parallel
4. Pushes to Artifact Registry
5. Deploys to Cloud Run

## How to Update an Environment Variable

1. Edit the local YAML file:

```bash
vim infra/cloudrun-env/code-service.yaml
```

2. Push the updated version to Secret Manager:

```bash
gcloud secrets versions add code-service-env \
  --data-file=infra/cloudrun-env/code-service.yaml \
  --project=gatepass-6d009
```

3. Trigger a deploy by pushing a commit to `main`, or manually run the Cloud Build trigger from the console.

## How to Add a New Environment Variable

1. Add the variable to the service's `config.py`:

```python
NEW_VAR: str = os.getenv("NEW_VAR", "default_value")
```

2. Add it to the service's env file at `infra/cloudrun-env/<service>.yaml`:

```yaml
NEW_VAR: "production_value"
```

3. Update the secret in Secret Manager:

```bash
gcloud secrets versions add <service>-env \
  --data-file=infra/cloudrun-env/<service>.yaml \
  --project=gatepass-6d009
```

4. Push your code changes to `main`. Cloud Build will pick up both the code change and the new secret.

The env checker (`bash infra/check-env.sh`) will catch mismatches. If you add a var to `config.py` but forget the YAML file (or vice versa), the build will warn you.

## Database Migrations

Migrations run automatically during Cloud Build deploys (before db-service is deployed). If you need to run one manually:

1. Start the Cloud SQL Auth Proxy (from the repo root):

```bash
./cloud-sql-proxy gatepass-6d009:europe-west1:gatepass-db --port=5433
```

2. In a separate terminal, run alembic:

```bash
cd services/db-service && \
DB_HOST=127.0.0.1 \
DB_PORT=5433 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=<YOUR_DB_PASSWORD> \
POSTGRES_DB=estate_code_db \
alembic upgrade head
```

To check current migration status:

```bash
cd services/db-service && \
DB_HOST=127.0.0.1 \
DB_PORT=5433 \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD=<YOUR_DB_PASSWORD> \
POSTGRES_DB=estate_code_db \
alembic current
```

## How to Deploy a Single Service Manually

```bash
bash infra/deploy-cloudrun.sh code-service
```

## Useful Commands

```bash
# Check all services
gcloud run services list --region=europe-west1 --project=gatepass-6d009

# View logs
gcloud run services logs read code-service --region=europe-west1 --project=gatepass-6d009 --limit=50

# Check recent builds
gcloud builds list --project=gatepass-6d009 --limit=5

# Validate env files locally
bash infra/check-env.sh

# Rollback to a previous revision
gcloud run revisions list --service=code-service --region=europe-west1 --project=gatepass-6d009
gcloud run services update-traffic code-service \
  --to-revisions=<REVISION_NAME>=100 \
  --region=europe-west1 \
  --project=gatepass-6d009
```

## Cost Summary

| Service        | Pricing Model                              |
| -------------- | ------------------------------------------ |
| Cloud Run      | Pay per request (generous free tier)       |
| Cloud SQL      | Small fixed cost (db-f1-micro instance)    |
| Upstash Redis  | Pay per request (near zero at low traffic) |
| Load Balancer  | Small fixed monthly cost                   |
| Secret Manager | A few cents per month                      |
| Cloud Build    | 120 free build-minutes per day             |

## Monolith Consolidation (Cost Optimization)

During early stages with low/zero traffic, all 7 services can be consolidated into a single Cloud Run container to reduce costs. This eliminates the overhead of 5+ always-on instances.

See the [Monolith Consolidation Guide](monolith-consolidation-guide.md) for the full plan, deployment steps, and instructions for reverting back to the distributed setup when traffic grows.

## Legacy GKE Scripts

The `infra/deploy.sh` and `infra/teardown.sh` scripts reference an earlier GKE-based deployment (project `gatepass-461616`, cluster `gatepass-cluster`). These are **not used** in the current Cloud Run setup and are kept for historical reference only.

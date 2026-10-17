#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Cloud Run deploy script for GatePass microservices.
#
# Usage:
#   bash infra/deploy-cloudrun.sh                 # deploy ALL services
#   bash infra/deploy-cloudrun.sh code-service    # deploy one service
#   bash infra/deploy-cloudrun.sh code-service ai-service  # deploy specific services
#
# Run from repo root.
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────
PROJECT_ID="gatepass-6d009"
REGION="europe-west1"
REPO="gatepass-repo"                         # Artifact Registry repo name
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
ENV_DIR="infra/cloudrun-env"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# ── Service definitions ──────────────────────────────────────────
# Map: Cloud Run service name → Dockerfile path
declare -A SVC_DOCKERFILE=(
  ["db-service"]="services/db-service/Dockerfile"
  ["cache-service"]="services/cache_service/Dockerfile"
  ["code-service"]="services/code_service/Dockerfile"
  ["user-profile-service"]="services/user_profile_service/Dockerfile"
  ["revenue-service"]="services/revenue_service/Dockerfile"
  ["ai-service"]="services/ai_service/Dockerfile"
  ["notification-service"]="services/notification_service/Dockerfile"
)

# Min instances per service (0 = scale to zero allowed)
declare -A SVC_MIN_INSTANCES=(
  ["db-service"]="1"
  ["cache-service"]="1"
  ["code-service"]="1"
  ["user-profile-service"]="1"
  ["revenue-service"]="0"
  ["ai-service"]="0"
  ["notification-service"]="0"
)

# Max instances per service
declare -A SVC_MAX_INSTANCES=(
  ["db-service"]="5"
  ["cache-service"]="3"
  ["code-service"]="10"
  ["user-profile-service"]="10"
  ["revenue-service"]="5"
  ["ai-service"]="5"
  ["notification-service"]="3"
)

# Memory per service
declare -A SVC_MEMORY=(
  ["db-service"]="512Mi"
  ["cache-service"]="256Mi"
  ["code-service"]="512Mi"
  ["user-profile-service"]="512Mi"
  ["revenue-service"]="512Mi"
  ["ai-service"]="1Gi"
  ["notification-service"]="256Mi"
)

# CPU per service
declare -A SVC_CPU=(
  ["db-service"]="1"
  ["cache-service"]="1"
  ["code-service"]="1"
  ["user-profile-service"]="1"
  ["revenue-service"]="1"
  ["ai-service"]="1"
  ["notification-service"]="1"
)

# Services that need Cloud SQL proxy sidecar
CLOUD_SQL_SERVICES=("db-service")
CLOUD_SQL_INSTANCE="${PROJECT_ID}:${REGION}:gatepass-db"

# Ingress settings per service
declare -A SVC_INGRESS=(
  ["db-service"]="internal"
  ["cache-service"]="internal"
  ["notification-service"]="internal"
  ["code-service"]="internal-and-cloud-load-balancing"
  ["user-profile-service"]="internal-and-cloud-load-balancing"
  ["revenue-service"]="internal-and-cloud-load-balancing"
  ["ai-service"]="internal-and-cloud-load-balancing"
)

# Deploy order (dependencies first)
DEPLOY_ORDER=("db-service" "cache-service" "notification-service" "revenue-service" "code-service" "user-profile-service" "ai-service")

# ── Helpers ──────────────────────────────────────────────────────
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

needs_cloud_sql() {
  local svc="$1"
  for s in "${CLOUD_SQL_SERVICES[@]}"; do
    [[ "$s" == "$svc" ]] && return 0
  done
  return 1
}

# ── Pre-flight checks ───────────────────────────────────────────
bold "Pre-flight checks..."

# gcloud authenticated?
if ! gcloud auth print-access-token &>/dev/null; then
  red "Not authenticated. Run: gcloud auth login"
  exit 1
fi

# Correct project?
ACTIVE_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [[ "$ACTIVE_PROJECT" != "$PROJECT_ID" ]]; then
  yellow "Switching project to ${PROJECT_ID}"
  gcloud config set project "$PROJECT_ID"
fi

# Artifact Registry repo exists?
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" &>/dev/null 2>&1; then
  bold "Creating Artifact Registry repo: ${REPO}"
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="GatePass container images"
fi

# Configure Docker auth for Artifact Registry
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet 2>/dev/null

# Run env checker
bold "Running env checker..."
if ! bash infra/check-env.sh; then
  red "Env check failed — fix errors before deploying."
  exit 1
fi

# ── Determine which services to deploy ───────────────────────────
if [[ $# -gt 0 ]]; then
  SERVICES_TO_DEPLOY=("$@")
  # Validate all requested services exist
  for svc in "${SERVICES_TO_DEPLOY[@]}"; do
    if [[ -z "${SVC_DOCKERFILE[$svc]+x}" ]]; then
      red "Unknown service: ${svc}"
      echo "Valid services: ${!SVC_DOCKERFILE[*]}"
      exit 1
    fi
  done
else
  SERVICES_TO_DEPLOY=("${DEPLOY_ORDER[@]}")
fi

bold "Deploying: ${SERVICES_TO_DEPLOY[*]}"
echo

# ── Build, push, deploy each service ────────────────────────────
FAILED=()
for svc in "${SERVICES_TO_DEPLOY[@]}"; do
  dockerfile="${SVC_DOCKERFILE[$svc]}"
  env_file="${ENV_DIR}/${svc}.yaml"
  image="${REGISTRY}/${svc}:${TIMESTAMP}"
  min="${SVC_MIN_INSTANCES[$svc]}"
  max="${SVC_MAX_INSTANCES[$svc]}"
  memory="${SVC_MEMORY[$svc]}"
  cpu="${SVC_CPU[$svc]}"
  ingress="${SVC_INGRESS[$svc]}"

  bold "━━━ ${svc} ━━━"

  # Check env file exists
  if [[ ! -f "$env_file" ]]; then
    red "  ✗ Missing env file: ${env_file} — skipping"
    FAILED+=("$svc")
    continue
  fi

  # Build
  echo "  Building ${image}..."
  if ! docker build -f "$dockerfile" --platform linux/amd64 -t "$image" . ; then
    red "  ✗ Build failed"
    FAILED+=("$svc")
    continue
  fi

  # Push
  echo "  Pushing to Artifact Registry..."
  if ! docker push "$image"; then
    red "  ✗ Push failed"
    FAILED+=("$svc")
    continue
  fi

  # Deploy
  echo "  Deploying to Cloud Run..."
  DEPLOY_CMD=(
    gcloud run deploy "$svc"
    --image="$image"
    --region="$REGION"
    --project="$PROJECT_ID"
    --env-vars-file="$env_file"
    --min-instances="$min"
    --max-instances="$max"
    --memory="$memory"
    --cpu="$cpu"
    --port=8080
    --ingress="$ingress"
    --allow-unauthenticated
    --quiet
  )

  # Add Cloud SQL sidecar if needed
  if needs_cloud_sql "$svc"; then
    DEPLOY_CMD+=(--add-cloudsql-instances="$CLOUD_SQL_INSTANCE")
  fi

  if ! "${DEPLOY_CMD[@]}"; then
    red "  ✗ Deploy failed"
    FAILED+=("$svc")
    continue
  fi

  green "  ✓ ${svc} deployed"
  echo
done

# ── Summary ──────────────────────────────────────────────────────
echo
bold "══════════════════════════════════════════════════"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  red "  Failed: ${FAILED[*]}"
  echo "  Succeeded: $(( ${#SERVICES_TO_DEPLOY[@]} - ${#FAILED[@]} )) / ${#SERVICES_TO_DEPLOY[@]}"
  exit 1
else
  green "  All ${#SERVICES_TO_DEPLOY[@]} services deployed successfully ✓"
  echo "  Timestamp: ${TIMESTAMP}"
fi

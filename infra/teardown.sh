#!/usr/bin/env bash
# Run from repository root: bash infra/teardown.sh
#
# Removes app-layer workloads (microservice Deployments/Services, migration Job),
# then deletes the GKE cluster. Postgres/Redis from gatepass-baseimage-*.yaml are not
# kubectl-deleted here (cluster delete still destroys them unless you remove that step).
# Container images in gcr.io are not removed.
#
# Safety: set CONFIRM=YES to skip the interactive prompt (e.g. CI).
# Example: CONFIRM=YES bash infra/teardown.sh

set -euo pipefail

PROJECT_ID="gatepass-461616"
CLUSTER_NAME="gatepass-cluster"
ZONE="us-central1-a"
BASE_SERVICES_FILE="infra/gatepass-baseimage-service.yaml"
DEPLOYMENT_FILE="infra/gatepass-microservice-deployment.yaml"
SERVICES_FILE="infra/gatepass-microservice-service.yaml"
MIGRATION_JOB="db-migration-gcp"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "${CONFIRM:-}" != "YES" ]]; then
    read -r -p "This will delete cluster '${CLUSTER_NAME}' and all Gatepass workloads in it. Continue? [y/N] " ans
    case "${ans}" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

echo "Project: ${PROJECT_ID}"

if ! gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
    echo "Cluster '${CLUSTER_NAME}' not found in ${ZONE}; nothing to tear down."
    exit 0
fi

gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID"

echo "Deleting migration Job..."
kubectl delete job "$MIGRATION_JOB" --ignore-not-found --wait=true

echo "Deleting microservice Deployments..."
kubectl delete -f "$DEPLOYMENT_FILE" --ignore-not-found --wait=true

echo "Deleting Services..."
kubectl delete -f "$SERVICES_FILE" --ignore-not-found --wait=true

echo "Deleting base Services..."
kubectl delete -f "$BASE_SERVICES_FILE" --ignore-not-found --wait=true

echo "Deleting GKE cluster '${CLUSTER_NAME}' (this can take several minutes)..."
gcloud container clusters delete "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet

echo "Teardown finished."

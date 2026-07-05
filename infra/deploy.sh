# Run from root directory using 'bash infra/deploy.sh'

# Configuration
PROJECT_ID="gatepass-461616"
CLUSTER_NAME="gatepass-cluster"
ZONE="us-central1-a"
REGISTRY_URL="gcr.io"
BASE_DEPLOYMENT_FILE="infra/gatepass-baseimage-deployment.yaml"
BASE_SERVICES_FILE="infra/gatepass-baseimage-service.yaml"
DEPLOYMENT_FILE="infra/gatepass-microservice-deployment.yaml"
SERVICES_FILE="infra/gatepass-microservice-service.yaml"
MIGRATION_FILE="infra/gatepass-migrations.yaml"
CERTIFICATE_FILE="infra/gatepass-certificate.yaml"
INGRESS_FILE="infra/gatepass-ingress.yaml"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Services configuration arrays
SERVICES=("cache-service-gcp" "code-service-gcp" "db-service-gcp" "db-migration-gcp" "user-profile-service-gcp")
DOCKERFILES=("services/cache_service/Dockerfile" "services/code_service/Dockerfile" "services/db-service/Dockerfile" "services/db-service/Dockerfile" "services/user_profile_service/Dockerfile")

# Authenticate with Google Cloud
# Checking if gcloud credentials are present, and ProjectID is set
echo
if grep -q $PROJECT_ID ~/.config/gcloud/application_default_credentials.json; then
    echo "Project is already set to $PROJECT_ID"
    echo
    echo "Checking if credentials are expired..."
    if ! gcloud auth application-default print-access-token > /dev/null 2>&1; then
        echo "Credentials expired. Reauthenticating..."
        gcloud auth login --quiet || true
        gcloud auth application-default login
    else
        echo "Already authenticated."
    fi
else
    gcloud config set project $PROJECT_ID
    gcloud auth application-default login
fi

# Build and tag service images
for i in "${!SERVICES[@]}"; do
    service="${SERVICES[$i]}"
    dockerfile="${DOCKERFILES[$i]}"
    tagged_image="${service}:${TIMESTAMP}"
    full_image_path="${REGISTRY_URL}/${PROJECT_ID}/${tagged_image}"

    # Build image
    docker build -f "$dockerfile" --platform linux/amd64 -t "$tagged_image" .

    # Tag for registry
    docker tag "$tagged_image" "$full_image_path"

    # Push to registry
    docker push "$full_image_path"
done

# Create cluster if it doesn't exist (re-running deploy when the cluster already exists is OK — this branch is skipped)
if ! gcloud container clusters describe $CLUSTER_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    gcloud container clusters create $CLUSTER_NAME \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --num-nodes=3 \
        --machine-type=e2-medium \
        --enable-autoscaling \
        --min-nodes=1 \
        --max-nodes=5
else
    echo "Cluster '${CLUSTER_NAME}' already exists in ${ZONE}; reusing it (no error)."
fi

# Get cluster credentials
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE --project=$PROJECT_ID

# Kubernetes Secrets from local .env.secrets (gitignored). Injects at runtime; images stay secret-free.
# Keys in .env.secrets become container env vars; explicit env: in deployments still overrides for cluster-specific values.
apply_secrets_from_env_files() {
    local file name
    while IFS= read -r line; do
        file="${line%%:*}"
        name="${line##*:}"
        if [[ -f "$file" ]]; then
            echo "Applying Secret ${name} from ${file}"
            kubectl create secret generic "$name" --from-env-file="$file" --dry-run=client -o yaml | kubectl apply -f -
        else
            echo "Skipping Secret ${name}: file not found (${file}). Copy .env.secrets into place or create the Secret manually."
        fi
    done <<'EOF'
services/cache_service/.env.secrets:cache-service-gcp-secrets
services/code_service/.env.secrets:code-service-gcp-secrets
services/db-service/.env.secrets:db-service-gcp-secrets
services/user_profile_service/.env.secrets:user-profile-service-gcp-secrets
EOF
}

apply_secrets_from_env_files

# GCS documents SA key (JSON file mount). Kept separate from apply_secrets_from_env_files
# because that helper only supports --from-env-file, not binary/JSON key files.
apply_gcs_documents_sa_secret() {
    local key_file="services/db-service/secrets/gatepass-461616-332b2d1bd5c1.json"
    local secret_name="db-service-gcs-sa"
    local key_name="gatepass-461616-332b2d1bd5c1.json"

    if [[ -f "$key_file" ]]; then
        echo "Applying Secret ${secret_name} from ${key_file}"
        kubectl create secret generic "$secret_name" \
            --from-file="${key_name}=${key_file}" \
            --dry-run=client -o yaml | kubectl apply -f -
    else
        echo "Skipping Secret ${secret_name}: file not found (${key_file}). Place the GCS SA key there before deploy."
    fi
}

apply_gcs_documents_sa_secret

# Postgres and Redis must exist before migrations (see infra/Note.txt). Skip baseimage apply if already healthy.
baseimage_already_up() {
    local r p
    r=$(kubectl get deploy redis -o jsonpath='{.status.availableReplicas}' 2>/dev/null) || return 1
    p=$(kubectl get deploy postgres -o jsonpath='{.status.availableReplicas}' 2>/dev/null) || return 1
    [[ "${r:-0}" -ge 1 ]] && [[ "${p:-0}" -ge 1 ]]
}

if baseimage_already_up; then
    echo "Redis and Postgres deployments are already available; skipping ${BASE_DEPLOYMENT_FILE} and ${BASE_SERVICES_FILE}."
else
    echo "Deploying Redis and Postgres (baseimage)..."
    kubectl apply -f $BASE_DEPLOYMENT_FILE
    kubectl apply -f $BASE_SERVICES_FILE
    kubectl rollout status deployment/redis --timeout=300s
    kubectl rollout status deployment/postgres --timeout=300s
fi

# Migrations before app pods so schema exists when services connect (no race on startup)
echo "Running database migrations..."
kubectl delete job db-migration-gcp --ignore-not-found --wait=true 2>/dev/null || true
cp $MIGRATION_FILE /tmp/migration-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/db-migration-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/db-migration-gcp:${TIMESTAMP}"'|g' /tmp/migration-temp.yaml
kubectl apply -f /tmp/migration-temp.yaml
echo "Waiting for migration to complete..."
if ! kubectl wait --for=condition=complete job/db-migration-gcp --timeout=300s; then
    echo "Migration failed or timed out. Checking logs..."
    kubectl logs job/db-migration-gcp --tail=200 2>/dev/null || kubectl logs job/db-migration-gcp
    exit 1
fi
echo "Migration completed successfully"

# Update deployment file with timestamped images
cp $DEPLOYMENT_FILE /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/cache-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/cache-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/code-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/code-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/db-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/db-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/user-profile-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/user-profile-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml

kubectl apply -f /tmp/deployment-temp.yaml
kubectl rollout status deployment/cache-service-gcp --timeout=300s
kubectl rollout status deployment/code-service-gcp --timeout=300s
kubectl rollout status deployment/db-service-gcp --timeout=300s
kubectl rollout status deployment/user-profile-service-gcp --timeout=300s

echo "Deploying Kubernetes services (ClusterIP for cache, code, db, user-profile; LoadBalancer only for db-service-gcp-external)..."
kubectl apply -f $SERVICES_FILE

echo "Waiting for db-service-gcp-external LoadBalancer IP (up to ~6m; GCP provisions network LB)..."
wait_lb_ip() {
    local svc="$1"
    local ip=""
    local i
    for ((i = 0; i < 36; i++)); do
        ip=$(kubectl get svc "$svc" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
        if [[ -n "$ip" ]]; then
            echo "$ip"
            return 0
        fi
        sleep 10
    done
    echo ""
    return 1
}

DB_LB_IP=$(wait_lb_ip db-service-gcp-external || true)

echo "ManagedCertificate and Ingress (api.gatepassng.com)..."
if kubectl get managedcertificate gatepass-cert &>/dev/null; then
    echo "ManagedCertificate gatepass-cert already exists; skipping kubectl apply -f ${CERTIFICATE_FILE}"
else
    kubectl apply -f "$CERTIFICATE_FILE"
fi
if kubectl get ingress gatepass-ingress &>/dev/null; then
    echo "Ingress gatepass-ingress already exists; skipping kubectl apply -f ${INGRESS_FILE}"
else
    kubectl apply -f "$INGRESS_FILE"
fi

echo ""
echo "ManagedCertificate status (TLS stays Pending until DNS points at the Ingress IP):"
kubectl describe managedcertificate gatepass-cert 2>/dev/null || echo "(no ManagedCertificate gatepass-cert yet)"
echo ""
echo "Ingress:"
kubectl get ingress gatepass-ingress -o wide 2>/dev/null || echo "(no Ingress gatepass-ingress yet)"

# Cleanup temporary files
rm -f /tmp/deployment-temp.yaml
rm -f /tmp/migration-temp.yaml

# Output deployment info
echo "Deployment completed with timestamp: $TIMESTAMP"
echo ""
echo "External (LoadBalancer):"
[[ -n "$DB_LB_IP" ]] && echo "  db-service: http://${DB_LB_IP}:9032/" || echo "  db-service: (pending — kubectl get svc db-service-gcp-external)"
echo ""
echo "In-cluster only (ClusterIP — use port-forward, Ingress, or another proxy to reach from outside):"
echo "  code-service:      http://code-service-gcp:9033/"
echo "  user-profile:      http://user-profile-service-gcp:9034/"
echo "  db-service:        http://db-service-gcp:9032/"
echo ""
echo "Deployments:"
kubectl get deployments
echo ""
echo "Services:"
kubectl get services
echo ""
echo "Migration Jobs:"
kubectl get jobs -l app=db-migration-gcp

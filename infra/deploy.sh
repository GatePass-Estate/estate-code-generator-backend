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

# Create cluster if it doesn't exist
if ! gcloud container clusters describe $CLUSTER_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    gcloud container clusters create $CLUSTER_NAME \
        --zone=$ZONE \
        --project=$PROJECT_ID \
        --num-nodes=3 \
        --machine-type=e2-medium \
        --enable-autoscaling \
        --min-nodes=1 \
        --max-nodes=5
fi

# Get cluster credentials
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE --project=$PROJECT_ID

# Postgres and Redis must exist before migrations or microservices can use DB/cache (see infra/Note.txt)
echo "Deploying Redis and Postgres..."
kubectl apply -f $BASE_DEPLOYMENT_FILE
kubectl apply -f $BASE_SERVICES_FILE
kubectl rollout status deployment/redis --timeout=300s
kubectl rollout status deployment/postgres --timeout=300s

# Migrations before app pods so schema exists when services connect (no race on startup)
echo "Running database migrations..."
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

echo "Deploying Kubernetes services (ClusterIP db + user-profile; LoadBalancers for db/user-profile external + code)..."
kubectl apply -f $SERVICES_FILE

echo "Waiting for LoadBalancer IPs (up to ~6m each; GCP provisions network LB)..."
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
CODE_LB_IP=$(wait_lb_ip code-service-gcp || true)
UP_LB_IP=$(wait_lb_ip user-profile-service-gcp-external || true)

if [[ -n "$UP_LB_IP" ]]; then
    kubectl set env deployment/user-profile-service-gcp BASE_URL="http://${UP_LB_IP}:9034/"
    echo "Set user-profile BASE_URL to http://${UP_LB_IP}:9034/ (use https + DNS when fronting with TLS)"
else
    echo "Note: user-profile-service-gcp-external has no EXTERNAL-IP yet. When ready: kubectl get svc user-profile-service-gcp-external"
    echo "  Then: kubectl set env deployment/user-profile-service-gcp BASE_URL=http://<EXTERNAL-IP>:9034/"
fi

# Cleanup temporary files
rm -f /tmp/deployment-temp.yaml
rm -f /tmp/migration-temp.yaml

# Output deployment info
echo "Deployment completed with timestamp: $TIMESTAMP"
echo ""
echo "LoadBalancer endpoints (http://IP:port — add DNS/TLS as needed):"
[[ -n "$DB_LB_IP" ]] && echo "  db-service (external): http://${DB_LB_IP}:9032/" || echo "  db-service (external): (pending — kubectl get svc db-service-gcp-external)"
echo "  db-service (in-cluster): http://db-service-gcp:9032"
[[ -n "$CODE_LB_IP" ]] && echo "  code-service:      http://${CODE_LB_IP}:9033/" || echo "  code-service:      (pending — kubectl get svc code-service-gcp)"
[[ -n "$UP_LB_IP" ]] && echo "  user-profile (external): http://${UP_LB_IP}:9034/" || echo "  user-profile (external): (pending — kubectl get svc user-profile-service-gcp-external)"
echo "  user-profile (in-cluster): http://user-profile-service-gcp:9034"
echo ""
echo "Deployments:"
kubectl get deployments
echo ""
echo "Services:"
kubectl get services
echo ""
echo "Migration Jobs:"
kubectl get jobs -l app=db-migration-gcp

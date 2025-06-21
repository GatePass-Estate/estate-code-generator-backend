# Run from root directory using 'bash infra/deploy.sh'

# Configuration
PROJECT_ID="gatepass-461616"
CLUSTER_NAME="estate-code-cluster"
ZONE="us-central1-a"
REGISTRY_URL="gcr.io"
DEPLOYMENT_FILE="infra/gatepass-microservice-deployment.yaml"
SERVICES_FILE="infra/gatepass-microservice-service.yaml"
MIGRATION_FILE="infra/gatepass-migrations.yaml"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Services configuration arrays
SERVICES=("cache-service-gcp" "code-service-gcp" "db-service-gcp" "db-migration-gcp")
DOCKERFILES=("services/cache_service/Dockerfile" "services/code_service/Dockerfile" "services/db-service/Dockerfile" "services/db-service/Dockerfile")

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

# Update deployment file with timestamped images
cp $DEPLOYMENT_FILE /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/cache-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/cache-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/code-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/code-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/db-service-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/db-service-gcp:${TIMESTAMP}"'|g' /tmp/deployment-temp.yaml

# Deploy services
kubectl apply -f /tmp/deployment-temp.yaml

# Wait for deployments to be ready
kubectl rollout status deployment/cache-service-gcp --timeout=300s
kubectl rollout status deployment/code-service-gcp --timeout=300s
kubectl rollout status deployment/db-service-gcp --timeout=300s

# Deploy Kubernetes services (LoadBalancer, ClusterIP, etc.)
echo "Deploying Kubernetes services..."
kubectl apply -f $SERVICES_FILE

# Run database migrations
echo "Running database migrations..."

# Create temporary migration file with substituted timestamp
cp $MIGRATION_FILE /tmp/migration-temp.yaml
sed -i '' 's|gcr.io/gatepass-461616/db-migration-gcp:latest|'"${REGISTRY_URL}/${PROJECT_ID}/db-migration-gcp:${TIMESTAMP}"'|g' /tmp/migration-temp.yaml

# Apply migration job
kubectl apply -f /tmp/migration-temp.yaml

# Wait for migration to complete
echo "Waiting for migration to complete..."
kubectl wait --for=condition=complete job/db-migration-gcp --timeout=300s

# Check if migration was successful
if kubectl get job db-migration-gcp -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null | grep -q "True"; then
    echo "Migration completed successfully"
else
    echo "Migration failed or timed out. Checking logs..."
    kubectl logs job/db-migration-gcp

    # Check if job failed
    if kubectl get job db-migration-gcp -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null | grep -q "True"; then
        echo "Migration job failed"
        exit 1
    fi
fi

# Cleanup temporary files
rm -f /tmp/deployment-temp.yaml
rm -f /tmp/migration-temp.yaml

# Output deployment info
echo "Deployment completed with timestamp: $TIMESTAMP"
echo ""
echo "Deployments:"
kubectl get deployments
echo ""
echo "Services:"
kubectl get services
echo ""
echo "Migration Jobs:"
kubectl get jobs -l app=db-migration-gcp

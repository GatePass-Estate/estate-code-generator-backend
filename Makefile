.PHONY: build build-staging build-fresh clean logs restart start stop gcp-deploy gcp-teardown prod-build prod-push prod-deploy prod-release prod-logs

clean:
	chmod +x ./scripts/clean.sh
	./scripts/clean.sh

clean-build: clean build

build:
	docker compose -f 'docker-compose.yaml' up -d --build
	$(MAKE) run_migrations

build-staging:
	docker compose -f 'docker-compose.yaml' up -d --build --force-recreate
	$(MAKE) run_migrations

build-fresh:
	docker compose -f 'docker-compose.yaml' build --no-cache
	docker compose -f 'docker-compose.yaml' up -d --force-recreate
	$(MAKE) run_migrations


start:
	docker compose --project-name estate-code up -d

stop:
	docker compose --project-name estate-code stop

restart: stop start

logs:
	docker compose --project-name composer_stack logs -f

clean-db:
	docker compose down estate_code_postgres
	docker volume rm estate_code_postgres_data
	docker compose up -d estate_code_postgres
	$(MAKE) run_migrations

# old run_migrations:
# 	docker compose exec db-service /bin/bash -c "alembic upgrade head"

run_migrations:
	docker compose up --no-start db-migration
	docker compose start db-migration

# ── Monolith (Cloud Run production) ──────────────────────────────
REGISTRY := europe-west1-docker.pkg.dev/gatepass-6d009/gatepass-repo
TIMESTAMP := $(shell date +%Y%m%d-%H%M%S)
IMAGE := $(REGISTRY)/gatepass-monolith:$(TIMESTAMP)

prod-build:
	docker build -f infra/monolith/Dockerfile --platform linux/amd64 \
	  --cache-from=$(REGISTRY)/gatepass-monolith:cache \
	  --build-arg BUILDKIT_INLINE_CACHE=1 \
	  -t $(IMAGE) \
	  -t $(REGISTRY)/gatepass-monolith:cache .

prod-push:
	docker push $(IMAGE)
	docker push $(REGISTRY)/gatepass-monolith:cache

prod-deploy:
	gcloud run deploy gatepass-monolith \
	  --image=$(IMAGE) \
	  --region=europe-west1 \
	  --env-vars-file=infra/cloudrun-env/gatepass-monolith.yaml \
	  --min-instances=1 --max-instances=5 \
	  --memory=2Gi --cpu=2 --port=8080 --timeout=300 \
	  --no-cpu-throttling \
	  --allow-unauthenticated \
	  --add-cloudsql-instances=gatepass-6d009:europe-west1:gatepass-db \
	  --service-account=db-service-sa@gatepass-6d009.iam.gserviceaccount.com \
	  --project=gatepass-6d009

# Build, push, and deploy in one command
prod-release: prod-build prod-push prod-deploy

prod-logs:
	gcloud run services logs read gatepass-monolith --region=europe-west1 --project=gatepass-6d009 --limit=50

# ── Legacy GKE (not used) ───────────────────────────────────────
gcp-deploy:
	bash infra/deploy.sh

gcp-teardown:
	bash infra/teardown.sh

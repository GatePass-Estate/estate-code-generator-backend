.PHONY: build build-staging build-fresh clean logs restart start stop gcp-deploy gcp-teardown

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

# GCP: run from repository root. build.sh writes infra/.gcp_image_tag; deploy.sh reads it.
gcp-deploy:
	bash infra/deploy.sh

# GCP: remove microservice Services/Deployments, migration Job, then delete the cluster (see infra/teardown.sh).
gcp-teardown:
	bash infra/teardown.sh

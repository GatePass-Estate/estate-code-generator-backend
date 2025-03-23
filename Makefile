.PHONY: build clean logs restart start stop

clean:
	chmod +x ./scripts/clean.sh
	./scripts/clean.sh

build: clean
	docker compose -f 'docker-compose.yaml' up -d --build
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

run_migrations:
	docker compose exec db-service /bin/bash -c "alembic upgrade head"

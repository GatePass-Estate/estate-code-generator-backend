build:
	docker compose -f 'docker-compose.yaml' up -d --build

.PHONY: start stop restart logs
start:
	docker compose --project-name estate-code up -d

stop:
	docker compose --project-name estate-code stop

restart: stop start

logs:
	docker compose --project-name composer_stack logs -f

clean:
	chmod +x ./scripts/clean.sh
	./scripts/clean.sh

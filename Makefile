build:
	docker compose -f 'docker-compose.yaml' up -d --build

clean:
	./scripts/clean.sh
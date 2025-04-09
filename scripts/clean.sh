#!/bin/bash

set -e

# prune the images within the compose stack (if they exist)
docker container inspect estate_code_postgres &>/dev/null && docker container rm -f estate_code_postgres
docker volume inspect estate_code_postgres_data &>/dev/null && docker volume rm estate_code_postgres_data
docker container inspect estate_code_redis &>/dev/null && docker container rm -f estate_code_redis
docker container inspect cache-service &>/dev/null && docker container rm -f cache-service
docker container inspect code-service &>/dev/null && docker container rm -f code-service
docker container inspect db-service &>/dev/null && docker container rm -f db-service
docker container inspect db-migration &>/dev/null && docker container rm -f db-migration

echo "clean done"

#!/bin/bash

set -e

# prune the images within the compose stack (if they exist)
docker container inspect estate_code_postgres &>/dev/null && docker container rm -f estate_code_postgres
docker volume inspect estate_code_postgres_data &>/dev/null && docker volume rm estate_code_postgres_data
docker container inspect db-service &>/dev/null && docker container rm -f db-service

echo "clean done"

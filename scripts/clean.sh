#!/bin/bash

set -e

# prune the images and not the compose stack
docker container rm -f estate_code_postgres || true

echo "clean done"

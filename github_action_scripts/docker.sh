#!/usr/bin/env bash

# Run from .github/workflows/docker.yml
# Build the CRATE Docker image

set -euxo pipefail

export CRATE_DOCKER_CONFIG_HOST_DIR=${HOME}/crate_config
export CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR=${HOME}/bioyodie_resources
export CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD=ramalamadingdong
export CRATE_DOCKER_MYSQL_ROOT_PASSWORD=shoobydoobydoo
export CRATE_DOCKER_INSTALL_USER_ID=$(id -u)
export CRATE_DOCKER_CRATEWEB_USE_HTTPS=0
cd docker/dockerfiles
docker compose version
docker compose build

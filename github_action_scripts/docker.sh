#!/usr/bin/env bash

# Run from .github/workflows/docker.yml
# Build the CRATE Docker image

set -euxo pipefail

cd docker/dockerfiles
docker compose version
docker compose build

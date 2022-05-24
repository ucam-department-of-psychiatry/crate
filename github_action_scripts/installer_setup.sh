#!/usr/bin/env bash

# Run from .github/workflows/installer.yml

set -euxo pipefail

sudo apt-get update
sudo apt -y install python3-virtualenv python3-venv wait-for-it
docker --version
docker compose version
mkdir "${CRATE_DOCKER_CONFIG_HOST_DIR}"

#!/usr/bin/env bash

# Run from .github/workflows/installer.yml
# Check various things after running the installer

set -euxo pipefail

# Check Django app is running
cd "${CRATE_HOME}/docker/dockerfiles"
docker compose logs
SERVER_IP=$(docker inspect crate_crate_server --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
wait-for-it "${SERVER_IP}:8000" --timeout=300
curl -I -L --retry 10 --fail --insecure "https://${SERVER_IP}:8000/crate/"
# Check static files collected
curl -I -L --fail --insecure "https://${SERVER_IP}:8000/crate_static/scrubber.png"
cd "${CRATE_HOME}/docker/dockerfiles"

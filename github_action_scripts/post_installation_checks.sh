#!/usr/bin/env bash

# Run from .github/workflows/installer.yml
# Check various things after running the installer

set -euxo pipefail

# Check Django app is running
cd "${CRATE_HOME}/docker/dockerfiles"
docker compose logs
SERVER_IP=$(docker inspect crate_crate_server --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
wait-for-it "${SERVER_IP}:8000" --timeout=300
curl -I -L --retry 10 --fail --insecure "${SERVER_IP}:8000/crate/"
# Check static files collected
curl -I -L --fail --insecure "${SERVER_IP}:8000/crate_static/scrubber.png"
cd "${CRATE_HOME}/docker/dockerfiles"
# Check anonymiser worked
anonymised=$(docker compose exec -T research_db mysql -Ns -u research -presearch research -e "SELECT SUBSTR(note, 1, 36) FROM note LIMIT 1")
[ "${anonymised}" = "\n[__PPP__] [__PPP__] lived on a farm" ]
# Check anonymisation API is working
anonymised=$(curl -L --fail -X POST $SERVER_IP:8000/crate/anon_api/scrub/ -H 'Content-Type: application/json' -d '{"text": {"test": "He was born on 1st January 1970"},"patient": {"dates": ["1970-01-01"]}}' | jq --raw-output '.anonymised.test')
[ "${anonymised}" == "He was born on [__PPP__]" ]

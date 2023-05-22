#!/usr/bin/env bash

# Run from .github/workflows/installer.yml
# Check anonymisation after running the installer with demo database

set -euxo pipefail

cd "${CRATE_HOME}/docker/dockerfiles"
# Check anonymiser worked
anonymised=$(docker compose -f docker-compose.yaml -f docker-compose-crate-db.yaml -f docker-compose-research-db.yaml -f docker-compose-secret-db.yaml -f docker-compose-source-db.yaml exec -T research_db mysql -Ns -u research -presearch research -e "SELECT SUBSTR(note, 1, 36) FROM note LIMIT 1")
[ "${anonymised}" = "\n[__PPP__] [__PPP__] lived on a farm" ]
# Check anonymisation API is working
anonymised=$(curl -L --fail -X POST $SERVER_IP:8000/crate/anon_api/scrub/ -H 'Content-Type: application/json' -d '{"text": {"test": "He was born on 1st January 1970"},"patient": {"dates": ["1970-01-01"]}}' | jq --raw-output '.anonymised.test')
[ "${anonymised}" == "He was born on [__PPP__]" ]

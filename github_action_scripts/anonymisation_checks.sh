#!/usr/bin/env bash

# Run from .github/workflows/installer.yml
# Check anonymisation after running the installer with demo database

set -euxo pipefail

cd "${CRATE_HOME}/docker/dockerfiles"
SERVER_IP=$(docker inspect crate_crate_server --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
# Check anonymiser worked
anonymised=$(docker compose exec -T research_db mysql -Ns -u research -presearch research -e "SELECT SUBSTR(note, 1, 39) FROM note LIMIT 1")
[ "${anonymised}" = "I saw [__PPP__] [__PPP__] on 2000-01-01" ]
# Check anonymisation API is working
anonymised=$(curl -L --fail --insecure -X POST https://$SERVER_IP:8000/crate/anon_api/scrub/ -H 'Content-Type: application/json' -d '{"text": {"test": "He was born on 1st January 1970"},"patient": {"dates": ["1970-01-01"]}}' | jq --raw-output '.anonymised.test')
[ "${anonymised}" == "He was born on [__PPP__]" ]

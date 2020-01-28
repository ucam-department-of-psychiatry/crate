#!/usr/bin/env bash
# semehr_start_elasticsearch.sh
set -e

# -----------------------------------------------------------------------------
# Fetch environment variables from our common source
# -----------------------------------------------------------------------------

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source "${THIS_DIR}/semehr_set_envvars.sh"

# -----------------------------------------------------------------------------
# Start Elasticsearch
# -----------------------------------------------------------------------------
# Start the containers (will fetch all necessary software the first time).
# Run in foreground mode, so we can see the log output.
echo "Starting Docker container: ${ELASTICSEARCH_COMPOSE}"
docker-compose -f "${ELASTICSEARCH_COMPOSE}" up

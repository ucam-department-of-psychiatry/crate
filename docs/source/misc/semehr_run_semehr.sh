#!/usr/bin/env bash
# semehr_run_semehr.sh
set -e

# -----------------------------------------------------------------------------
# Fetch environment variables from our common source
# -----------------------------------------------------------------------------

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source "${THIS_DIR}/semehr_set_envvars.sh"

# -----------------------------------------------------------------------------
# Run SemEHR (i.e. start, run, stop)
# -----------------------------------------------------------------------------
docker-compose -f "${SEMEHR_COMPOSE}" run semehr

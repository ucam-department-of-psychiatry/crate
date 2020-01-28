#!/usr/bin/env bash
# semehr_set_envvars.sh

# -----------------------------------------------------------------------------
# Environment variables
# -----------------------------------------------------------------------------

# We will make this directory:
export TUTORIALDIR=${HOME}/tmp/semehr_tutorial1

# This should already exist and contain your Bio-YODIE installation:
export BIOYODIEDIR=${HOME}/dev/yodie-pipeline-1-2-umls-only

# Other directories and files we'll use:
# - Root directory of SemEHR Git repository
export GITDIR=${TUTORIALDIR}/CogStack-SemEHR
# - Docker Compose tutorial directory within SemEHR tree
export COMPOSEDIR=${GITDIR}/tutorials/tutorial1_compose_files
# - Docker Compose file to launch Elasticsearch
export ELASTICSEARCH_COMPOSE=${COMPOSEDIR}/semehr-tutorial1-servers-compose.yml
# - Docker Compose file to launch SemEHR
export SEMEHR_COMPOSE=${COMPOSEDIR}/semehr-tutorial-run-compose.yml
# - Data directory
export DATADIR=${GITDIR}/tutorials/mtsamples-cohort
# - SemEHR config file
export SEMEHR_CONFIG=${DATADIR}/semehr_settings.json
# - Docker network name
export NETNAME=semehrnet

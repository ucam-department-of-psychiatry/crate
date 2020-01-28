#!/usr/bin/env bash
# semehr_setup_demo.sh
set -e
# ... if we try to run this more than once, it will (appropriately) fail

# -----------------------------------------------------------------------------
# Fetch environment variables from our common source
# -----------------------------------------------------------------------------

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source "${THIS_DIR}/semehr_set_envvars.sh"

# -----------------------------------------------------------------------------
# Other variables:
# -----------------------------------------------------------------------------

grep sse4_2 /proc/cpuinfo >/dev/null && HAS_SSE42=true || HAS_SSE42=false

# -----------------------------------------------------------------------------
# Setup actions
# -----------------------------------------------------------------------------

echo "- Making directory: ${TUTORIALDIR}"
mkdir "${TUTORIALDIR}"

echo "- Copying in UMLS..."
cp -R "${BIOYODIEDIR}/bio-yodie-resources" "${TUTORIALDIR}"

echo "- Fetching SemEHR code..."
git clone https://github.com/CogStack/CogStack-SemEHR.git "${GITDIR}"

echo "- Copying/editing Docker Compose files..."
# - Point to our files, not some hard-coded root-based path:
sed -i "s,device: /semehr_tutorial1/,device: ${TUTORIALDIR}/,g" "${ELASTICSEARCH_COMPOSE}"
sed -i "s,device: /semehr_tutorial1/,device: ${TUTORIALDIR}/,g" "${SEMEHR_COMPOSE}"
# - Fix networking aspects of config files
#   (a) Create named network for Elasticsearch.
#       Cannot name network to be created in v2.2 of the Docker Compose
#       file format. Therefore, create it separately.
docker network create "${NETNAME}" || echo "- Docker network ${NETNAME} already exists."
#       ... and declare it as external:
cat <<EOT >> "${ELASTICSEARCH_COMPOSE}"
networks:
  default:
    external:
      name: ${NETNAME}
EOT
#   (b) Make SemEHR join that network.
cat <<EOT >> "${SEMEHR_COMPOSE}"
networks:
  default:
    external:
      name: ${NETNAME}
EOT
#   (c) Make config file use internal net and names, not main net and IP addresses.
sed -i "s,http://172.17.0.1:8200/,http://es01:9200/,g" "${SEMEHR_CONFIG}"
# - Disable machine learning libraries if SSE4.2 not supported
if [ "${HAS_SSE42}" = false ] ; then
    sed -i "s,environment:,environment:\n      - xpack.security.enabled=false\n      - xpack.monitoring.enabled=false\n      - xpack.ml.enabled=false\n      - xpack.graph.enabled=false\n      - xpack.watcher.enabled=false,g" "${ELASTICSEARCH_COMPOSE}"
fi
# - NB to revert files, use
#   cd "${GITDIR}"; git reset --hard origin/master

echo "- Done."

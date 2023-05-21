#!/usr/bin/env bash

# Run from .github/workflows/installer.yml

set -euxo pipefail

sudo apt-get update
sudo apt -y install python3-virtualenv python3-venv wait-for-it
docker --version
docker compose version
mkdir "${CRATE_DOCKER_CONFIG_HOST_DIR}"
mkdir "${CRATE_DOCKER_STATIC_HOST_DIR}"

SSL_CSR=${HOME}/crate.csr

openssl genrsa -out ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} 2048
openssl req -new -key ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} -out ${SSL_CSR} -subj "/C=GB/ST=Cambridgeshire/L=Cambridge/O=University of Cambridge/CN=localhost"
openssl x509 -req -days 36500 -in ${SSL_CSR} -signkey ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} -out ${CRATE_INSTALLER_CRATEWEB_SSL_CERTIFICATE}

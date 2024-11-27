#!/usr/bin/env bash

# Run from .github/workflows/installer.yml

set -euxo pipefail

sudo apt-get update
sudo apt -y install python3-virtualenv python3-venv wait-for-it
sudo mkdir ${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}
sudo chown $(id -u -n) ${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}

CERTS_DIR=${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/certs
CONFIG_DIR=${CRATE_INSTALLER_CRATE_ROOT_HOST_DIR}/config
mkdir ${CERTS_DIR}
mkdir ${CONFIG_DIR}

cp ${GITHUB_WORKSPACE}/github_action_scripts/odbc_user.ini ${CONFIG_DIR}

SSL_CSR=${CERTS_DIR}/crate.csr

openssl genrsa -out ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} 2048
openssl req -new -key ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} -out ${SSL_CSR} -subj "/C=GB/ST=Cambridgeshire/L=Cambridge/O=University of Cambridge/CN=localhost"
openssl x509 -req -days 36500 -in ${SSL_CSR} -signkey ${CRATE_INSTALLER_CRATEWEB_SSL_PRIVATE_KEY} -out ${CRATE_INSTALLER_CRATEWEB_SSL_CERTIFICATE}

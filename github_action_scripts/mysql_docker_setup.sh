#!/usr/bin/env bash

# Run from .github/workflows/installer.yml

set -euxo pipefail

sudo apt -y install gnutls-bin
sudo sed -i "s/^bind-address.*/bind-address = 0.0.0.0/" /etc/mysql/mysql.conf.d/mysqld.cnf
cat /etc/mysql/mysql.conf.d/mysqld.cnf
sudo service mysql start
mysql --raw -e "CREATE DATABASE ${CRATE_DOCKER_CRATE_DB_DATABASE_NAME};" -uroot -proot
mysql --raw -e "CREATE USER '${CRATE_DOCKER_CRATE_DB_USER_NAME}'@'%' IDENTIFIED WITH mysql_native_password BY '${CRATE_DOCKER_CRATE_DB_USER_PASSWORD}';" -uroot -proot
mysql --raw -e "GRANT ALL PRIVILEGES ON ${CRATE_DOCKER_CRATE_DB_DATABASE_NAME}.* TO '${CRATE_DOCKER_CRATE_DB_USER_NAME}'@'%';" -uroot -proot

mysql --raw -e "CREATE DATABASE ${CRATE_INSTALLER_RESEARCH_DATABASE_NAME};" -uroot -proot
mysql --raw -e "CREATE USER '${CRATE_INSTALLER_RESEARCH_DATABASE_USER_NAME}'@'%' IDENTIFIED WITH mysql_native_password BY '${CRATE_INSTALLER_RESEARCH_DATABASE_USER_PASSWORD}';" -uroot -proot
mysql --raw -e "GRANT ALL PRIVILEGES ON ${CRATE_INSTALLER_RESEARCH_DATABASE_NAME}.* TO '${CRATE_INSTALLER_RESEARCH_DATABASE_USER_NAME}'@'%';" -uroot -proot

mysql --raw -e "CREATE DATABASE ${CRATE_INSTALLER_SECRET_DATABASE_NAME};" -uroot -proot
mysql --raw -e "CREATE USER '${CRATE_INSTALLER_SECRET_DATABASE_USER_NAME}'@'%' IDENTIFIED WITH mysql_native_password BY '${CRATE_INSTALLER_SECRET_DATABASE_USER_PASSWORD}';" -uroot -proot
mysql --raw -e "GRANT ALL PRIVILEGES ON ${CRATE_INSTALLER_SECRET_DATABASE_NAME}.* TO '${CRATE_INSTALLER_SECRET_DATABASE_USER_NAME}'@'%';" -uroot -proot

mysql --raw -e "CREATE DATABASE ${CRATE_INSTALLER_SOURCE_DATABASE_NAME};" -uroot -proot
mysql --raw -e "CREATE USER '${CRATE_INSTALLER_SOURCE_DATABASE_USER_NAME}'@'%' IDENTIFIED WITH mysql_native_password BY '${CRATE_INSTALLER_SOURCE_DATABASE_USER_PASSWORD}';" -uroot -proot
mysql --raw -e "GRANT ALL PRIVILEGES ON ${CRATE_INSTALLER_SOURCE_DATABASE_NAME}.* TO '${CRATE_INSTALLER_SOURCE_DATABASE_USER_NAME}'@'%';" -uroot -proot

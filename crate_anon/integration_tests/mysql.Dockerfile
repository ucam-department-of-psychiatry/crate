# tests/sqlserver.Dockerfile
#
# Docker image that provides MySQL.

# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------

# Not this one:
#   FROM mysql/mysql-server:latest
# because apt-get is missing; see https://stackoverflow.com/questions/72946649.
FROM mysql:5.7-debian

# -----------------------------------------------------------------------------
# Variable setup
# -----------------------------------------------------------------------------

# From the outside world (i.e. the Python script):

# Database users/passwords:
ARG DB_ROOT_PASSWORD
ARG DB_PRIVUSER_USER
ARG DB_PRIVUSER_PASSWORD
ARG DB_RESEARCHER_USER
ARG DB_RESEARCHER_PASSWORD
ARG DB_TEST_USER
ARG DB_TEST_PASSWORD

# Database names:
ARG DB_SRC
ARG DB_ANON
ARG DB_SECRET
ARG DB_NLP
ARG DB_CRATE
ARG DB_TEST

# Used internally:

ARG UNIX_DB_USER=mysql
ARG PORT=3306
ARG DB_ROOT_USER=root

ARG SQLFILE=/_crate_create_databases.sql
ARG STARTUP_SCRIPT=/_crate_setupdb.sh
ARG ENTRYPOINT_SCRIPT=/_crate_entrypoint.sh


# -----------------------------------------------------------------------------
# Script contents
# -----------------------------------------------------------------------------

# - "%" in the context of users meaning "from any host"; "localhost" isn't
#   enough for the host machine to connect through.
ARG SQL="\n\
CREATE USER '${DB_PRIVUSER_USER}'@'%' IDENTIFIED WITH mysql_native_password BY '${DB_PRIVUSER_PASSWORD}';\n\
CREATE USER '${DB_RESEARCHER_USER}'@'%' IDENTIFIED WITH mysql_native_password BY  '${DB_RESEARCHER_PASSWORD}';\n\
CREATE USER '${DB_TEST_USER}'@'%' IDENTIFIED WITH mysql_native_password BY  '${DB_TEST_PASSWORD}';\n\
\n\
CREATE DATABASE ${DB_SRC};\n\
GRANT ALL ON ${DB_SRC}.* TO '${DB_PRIVUSER_USER}'@'%';\n\
\n\
CREATE DATABASE ${DB_ANON};\n\
GRANT ALL ON ${DB_ANON}.* TO '${DB_PRIVUSER_USER}'@'%';\n\
GRANT SELECT ON ${DB_ANON}.* TO '${DB_RESEARCHER_USER}'@'%';\n\
\n\
CREATE DATABASE ${DB_SECRET};\n\
GRANT ALL ON ${DB_SECRET}.* TO '${DB_PRIVUSER_USER}'@'%';\n\
\n\
CREATE DATABASE ${DB_NLP};\n\
GRANT ALL ON ${DB_NLP}.* TO '${DB_PRIVUSER_USER}'@'%';\n\
GRANT SELECT ON ${DB_NLP}.* TO '${DB_RESEARCHER_USER}'@'%';\n\
\n\
CREATE DATABASE ${DB_CRATE};\n\
GRANT ALL ON ${DB_CRATE}.* TO '${DB_PRIVUSER_USER}'@'%';\n\
\n\
CREATE DATABASE ${DB_TEST};\n\
GRANT ALL ON ${DB_TEST}.* TO '${DB_TEST_USER}'@'%';\n\
"

ARG STARTUP_SCRIPT_CONTENTS="#!bin/bash\n\
set -e  # exit on error\n\
# set -x  # echo commands\n\
\n\
echo '>>> Waiting for MySQL to launch on port ${PORT}...'\n\
until nc -z localhost ${PORT}; do\n\
    echo '>>> ... waiting...'\n\
    sleep 1.0  # wait time in seconds\n\
done\n\
\n\
echo '>>> MySQL is ready. Creating databases'\n\
mysql --host=localhost --port=${PORT} --user=${DB_ROOT_USER} --password=${DB_ROOT_PASSWORD} < '${SQLFILE}'\n\
# In a non-demo environment one would delete this sensitive script:\n\
# rm '${SQLFILE}'\n\
echo '>>> Databases created. READY.'\n\
"

ARG ENTRYPOINT_SCRIPT_CONTENTS="#!/bin/bash\n\
set -e  # exit on error\n\
${STARTUP_SCRIPT} &\n\
# This script is part of the original MySQL Docker image.\n\
# Using --general-log=1 is verbose but helpful for debugging.\n\
/usr/local/bin/docker-entrypoint.sh mysqld --general-log=1 \n\
"


# -----------------------------------------------------------------------------
# Install and add scripts
# -----------------------------------------------------------------------------

USER root
WORKDIR /

# Installation:
# - signature: https://stackoverflow.com/questions/66400254
# - iputils-ping for "ping" (for testing
# - netcat for "nc"
# - nano for debugging!
# - Additional complexity:
#   - Signature missing from default setup.
#   - Neither curl nor wget installed.
#   - Can't install without "update" first.
#   - Can't fetch signature, therefore. So must disable initial checks.
#   - But -- this is a faff -- just allow unauthenticated.

RUN apt-get update --allow-insecure-repositories \
    && apt-get install -y  \
        iputils-ping \
        netcat \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/ \
    \
    && echo "${SQL}" > "${SQLFILE}" \
    && chown "${UNIX_DB_USER}" "${SQLFILE}" \
    && chmod a+x "${SQLFILE}" \
    \
    && echo "${STARTUP_SCRIPT_CONTENTS}" > "${STARTUP_SCRIPT}" \
    && chown "${UNIX_DB_USER}" "${STARTUP_SCRIPT}" \
    && chmod a+x "${STARTUP_SCRIPT}" \
    \
    && echo "${ENTRYPOINT_SCRIPT_CONTENTS}" > "${ENTRYPOINT_SCRIPT}" \
    && chown "${UNIX_DB_USER}" "${ENTRYPOINT_SCRIPT}" \
    && chmod a+x "${ENTRYPOINT_SCRIPT}"


# -----------------------------------------------------------------------------
# Return to default database user; create database
# -----------------------------------------------------------------------------

USER "${UNIX_DB_USER}"

ENV MYSQL_ROOT_PASSWORD=${DB_ROOT_PASSWORD}
# ... this environment variable name is fixed and picked up by MySQL when it
# starts

EXPOSE ${PORT}

ENV DOCKER_ENTRYPOINT_SCRIPT=${ENTRYPOINT_SCRIPT}
CMD ["bash", "-c", "${DOCKER_ENTRYPOINT_SCRIPT}"]

# tests/sqlserver.Dockerfile
#
# Docker image that provides PostgreSQL (Postgres).

# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------

FROM postgres:13-bullseye

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

# Database names:
ARG DB_SRC
ARG DB_ANON
ARG DB_NLP

# Used internally:

ARG UNIX_DB_USER=postgres
ARG PORT=5432
ARG DB_ROOT_USER=postgres

ARG SQLFILE=/_crate_create_databases.sql
ARG STARTUP_SCRIPT=/_crate_setupdb.sh
ARG ENTRYPOINT_SCRIPT=/_crate_entrypoint.sh


# -----------------------------------------------------------------------------
# Script contents
# -----------------------------------------------------------------------------

ARG RESEARCHDB=researchdb
ARG SQL="\n\
CREATE USER ${DB_PRIVUSER_USER} WITH PASSWORD'${DB_PRIVUSER_PASSWORD}';\n\
CREATE USER ${DB_RESEARCHER_USER} WITH PASSWORD '${DB_RESEARCHER_PASSWORD}';\n\
\n\
CREATE DATABASE ${DB_SRC};\n\
GRANT ALL PRIVILEGES ON DATABASE ${DB_SRC} TO ${DB_PRIVUSER_USER};\n\
\n\
CREATE DATABASE ${DB_ANON};\n\
GRANT ALL PRIVILEGES ON DATABASE ${DB_ANON} TO ${DB_PRIVUSER_USER};\n\
GRANT CONNECT ON DATABASE ${DB_ANON} TO ${DB_RESEARCHER_USER};\n\
GRANT SELECT ON ALL TABLES IN SCHEMA ${DB_ANON} TO ${DB_RESEARCHER_USER};\n\
\n\
CREATE DATABASE ${DB_NLP};\n\
GRANT ALL PRIVILEGES ON DATABASE ${DB_NLP} TO ${DB_PRIVUSER_USER};\n\
GRANT CONNECT ON DATABASE ${DB_NLP} TO ${DB_RESEARCHER_USER};\n\
GRANT SELECT ON ALL TABLES IN SCHEMA ${DB_NLP} TO ${DB_RESEARCHER_USER};\n\
"

ARG STARTUP_SCRIPT_CONTENTS="#!bin/bash\n\
set -e  # exit on error\n\
# set -x  # echo commands\n\
\n\
echo '>>> Waiting for PostgreSQL to launch on port ${PORT}...'\n\
until nc -z localhost ${PORT}; do\n\
    echo '>>> ... waiting...'\n\
    sleep 1.0  # wait time in seconds\n\
done\n\
\n\
echo '>>> PostgreSQL is ready. Creating databases'\n\
PGPASSWORD=${DB_ROOT_PASSWORD} psql --host=localhost --port=${PORT} --username=${DB_ROOT_USER} < '${SQLFILE}'\n\
# In a non-demo environment one would delete this sensitive script:\n\
# rm '${SQLFILE}'\n\
echo '>>> Databases created. READY.'\n\
"

ARG ENTRYPOINT_SCRIPT_CONTENTS="#!/bin/bash\n\
set -e  # exit on error\n\
${STARTUP_SCRIPT} &\n\
/usr/local/bin/docker-entrypoint.sh postgres \n\
"


# -----------------------------------------------------------------------------
# Install and add scripts
# -----------------------------------------------------------------------------

USER root
WORKDIR /

# Installation:
# - iputils-ping for "ping" (for testing
# - netcat for "nc"

RUN apt-get update \
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

ENV POSTGRES_PASSWORD=${DB_ROOT_PASSWORD}
# ... this environment variable name is fixed and picked up by PostgreSQL when
# it starts

EXPOSE ${PORT}

ENV DOCKER_ENTRYPOINT_SCRIPT=${ENTRYPOINT_SCRIPT}
CMD ["bash", "-c", "${DOCKER_ENTRYPOINT_SCRIPT}"]

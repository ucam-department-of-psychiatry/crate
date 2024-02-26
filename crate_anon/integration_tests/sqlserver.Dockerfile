# tests/sqlserver.Dockerfile
#
# Docker image that provides Microsoft SQL Server.

# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------

FROM mcr.microsoft.com/mssql/server:2022-latest
# It's Ubuntu 2022.04.3 (as of Jan 2024).
# https://learn.microsoft.com/en-us/sql/linux/quickstart-install-connect-docker


# -----------------------------------------------------------------------------
# Variable setup
# -----------------------------------------------------------------------------
# - Note that FROM wipes ARG commands:
#   https://stackoverflow.com/questions/44438637/arg-substitution-in-run-command-not-working-for-dockerfile
#   ... re-fetch as "ARG VARNAME" after "FROM" if required.
# - ARG values can be specified to Docker ("docker build --build_arg key=value").
# - ARG values with no default must be specified from "outside", by our caller.
# - Here we also use ARG values as internal variables. That means they could
#   be inappropriately overriden by our caller, but they're better than ENV
#   variables in that they are not exposed to the "insides" of the Docker
#   container.

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
ARG DB_NLP
ARG DB_TEST

# Used internally:

ARG UNIX_DB_USER=mssql
ARG PORT=1433
ARG DB_ROOT_USER=sa

ARG SQLFILE=/_crate_create_databases.sql
ARG STARTUP_SCRIPT=/_crate_setupdb.sh
ARG ENTRYPOINT_SCRIPT=/_crate_entrypoint.sh
ARG SQLSERVER_LOGDIR=/var/log/_sqlserver
ARG SQLSERVER_LOG=${SQLSERVER_LOGDIR}/_sqlserver.log


# -----------------------------------------------------------------------------
# Script contents
# -----------------------------------------------------------------------------

# https://stackoverflow.com/questions/69941444/how-to-have-docker-compose-init-a-sql-server-database
# https://stackoverflow.com/questions/6688880/how-do-i-grant-read-access-for-a-user-to-a-database-in-sql-server
# https://stackoverflow.com/questions/27599839/how-to-wait-for-an-open-port-with-netcat
# https://github.com/mcmoe/mssqldocker

# Use double quotes for the outer aspects:
# (a) this enables ARG variable substitution;
# (b) this enables single quotes for the inner SQL literals.
ARG SQL="\n\
CREATE LOGIN [${DB_PRIVUSER_USER}] WITH PASSWORD = '${DB_PRIVUSER_PASSWORD}';\n\
GO\n\
CREATE LOGIN [${DB_RESEARCHER_USER}] WITH PASSWORD = '${DB_RESEARCHER_PASSWORD}';\n\
GO\n\
CREATE LOGIN [${DB_TEST_USER}] WITH PASSWORD = '${DB_TEST_PASSWORD}';\n\
GO\n\
\n\
CREATE DATABASE [${DB_SRC}];\n\
GO\n\
USE [${DB_SRC}];\n\
CREATE USER [${DB_PRIVUSER_USER}] FOR LOGIN [${DB_PRIVUSER_USER}];\n\
EXEC sp_addrolemember 'db_owner', '${DB_PRIVUSER_USER}';\n\
GO\n\
\n\
CREATE DATABASE [${DB_ANON}];\n\
GO\n\
USE [${DB_ANON}];\n\
CREATE USER [${DB_PRIVUSER_USER}] FOR LOGIN [${DB_PRIVUSER_USER}];\n\
EXEC sp_addrolemember 'db_owner', '${DB_PRIVUSER_USER}';\n\
CREATE USER [${DB_RESEARCHER_USER}] FOR LOGIN [${DB_RESEARCHER_USER}];\n\
EXEC sp_addrolemember 'db_datareader', '${DB_RESEARCHER_USER}';\n\
GO\n\
\n\
CREATE DATABASE [${DB_NLP}];\n\
GO\n\
USE [${DB_NLP}];\n\
CREATE USER [${DB_PRIVUSER_USER}] FOR LOGIN [${DB_PRIVUSER_USER}];\n\
EXEC sp_addrolemember 'db_owner', '${DB_PRIVUSER_USER}';\n\
CREATE USER [${DB_RESEARCHER_USER}] FOR LOGIN [${DB_RESEARCHER_USER}];\n\
EXEC sp_addrolemember 'db_datareader', '${DB_RESEARCHER_USER}';\n\
GO\n\
\n\
CREATE DATABASE [${DB_TEST}];\n\
GO\n\
USE [${DB_TEST}];\n\
CREATE USER [${DB_TEST_USER}] FOR LOGIN [${DB_TEST_USER}];\n\
EXEC sp_addrolemember 'db_owner', '${DB_TEST_USER}';\n\
GO\n\
\n\
GO\n\
"

ARG STARTUP_SCRIPT_CONTENTS="#!bin/bash\n\
set -e  # exit on error\n\
\n\
echo '>>> Waiting for SQL Server to launch on port ${PORT}...'\n\
until nc -z localhost ${PORT}; do\n\
    echo '>>> ... waiting (phase 1)...'\n\
    sleep 1.0  # wait time in seconds\n\
done\n\
echo '>>> SQL Server is up on port ${PORT}'\n\
echo '>>> Waiting for database setup to finish...'\n\
until grep 'Recovery is complete' '${SQLSERVER_LOG}' >/dev/null 2>/dev/null; do\n\
    echo '>>> ... waiting (phase 2)...'\n\
    ls -al '${SQLSERVER_LOG}'\n\
    sleep 1.0\n\
done\n\
\n\
echo '>>> SQL Server is ready. Creating databases'\n\
sqlcmd -S localhost -U '${DB_ROOT_USER}' -P '${DB_ROOT_PASSWORD}' -i '${SQLFILE}'\n\
# In a non-demo environment one would delete this sensitive script:\n\
# rm '${SQLFILE}'\n\
echo '>>> Databases created. READY.'\n\
"

ARG ENTRYPOINT_SCRIPT_CONTENTS="#!/bin/bash\n\
set -e  # exit on error\n\
${STARTUP_SCRIPT} &\n\
/opt/mssql/bin/sqlservr 2>&1 | tee '${SQLSERVER_LOG}'\n\
"


# -----------------------------------------------------------------------------
# Install and add scripts
# -----------------------------------------------------------------------------

USER root
ENV ACCEPT_EULA=Y
WORKDIR /

# Installation:
# - iputils-ping for "ping" (for testing
# - mssql-tools, for "sqlcmd" etc.:
#   https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-setup-tools?view=sql-server-ver16
# - netcat for "nc"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        iputils-ping \
        netcat \
    && curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        mssql-tools18 unixodbc-dev \
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
    && chmod a+x "${ENTRYPOINT_SCRIPT}" \
    \
    && mkdir -p "${SQLSERVER_LOGDIR}" \
    && chown "${UNIX_DB_USER}" "${SQLSERVER_LOGDIR}"


# -----------------------------------------------------------------------------
# Return to default database user; create database
# -----------------------------------------------------------------------------

USER "${UNIX_DB_USER}"

ENV PATH="${PATH}:/opt/mssql-tools/bin/"
ENV SA_PASSWORD=${DB_ROOT_PASSWORD}
# ... this environment variable name is fixed and picked up by SQL Server when
# it starts

EXPOSE ${PORT}
# EXPOSE means "expose to other containers in the same network" (rather than
# to the host).

# CMD vs ENTRYPOINT: see https://docs.docker.com/engine/reference/builder/
# To use an ARG in CMD, copy it to an ENV variable:
ENV DOCKER_ENTRYPOINT_SCRIPT=${ENTRYPOINT_SCRIPT}
CMD ["bash", "-c", "${DOCKER_ENTRYPOINT_SCRIPT}"]

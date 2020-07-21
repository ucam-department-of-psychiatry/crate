# server/docker/dockerfiles/camcops.Dockerfile
#
# Directory structure in container:
#
#   /camcops            All CamCOPS code/binaries.
#       /cfg            Config files are mounted here.
#       /src            Source code for CamCOPS server.
#       /venv           Python 3 virtual environment.
#           /bin        Main "camcops_server" executable lives here.


# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------
# - Avoid Alpine Linux?
#   https://pythonspeed.com/articles/base-image-python-docker-images/
# - python:3.6-slim-buster? This is a Debian distribution ("buster" is Debian
#   10). Seems to work fine.
# - ubuntu:18.04? Requires "apt install python3" or similar? Quite tricky.
#   Also larger.

FROM python:3.6-slim-buster

# FROM python:3.6-buster
# ... includes some things we need, but is LARGER overall.


# -----------------------------------------------------------------------------
# ADD: files to copy
# -----------------------------------------------------------------------------
# - Syntax: ADD <host_file_spec> <container_dest_dir>
# - The host file spec is relative to the context (and can't go "above" it).
# - This docker file lives in the "server/docker/dockerfiles" directory within
#   the CamCOPS source, so we expect Docker to be told (externally -- see e.g.
#   the Docker Compose file) that the context is a higher directory, "server/".
#   That is the directory containing "setup.py" and therefore the installation
#   directory for our Python package.
# - So in short, here we refer to the context as ".".

ADD . /crate/src


# -----------------------------------------------------------------------------
# WORKDIR: Set working directory on container.
# -----------------------------------------------------------------------------
# Shouldn't really be necessary.

WORKDIR /crate


# -----------------------------------------------------------------------------
# RUN: run a command.
# -----------------------------------------------------------------------------
# - See notes in the corresponding CamCOPS files.
# - mmh3 needs g++ as well as gcc.
# - pdftotext is part of poppler-utils.
# - unixodbc-dev is required for the Python pyodbc package (or: missing sql.h).
# - Java for GATE (but default-jdk didn't work)...
#   ... in fact the problem is that you need
#   mkdir -p /usr/share/man/man1 /usr/share/man/man2
#   https://stackoverflow.com/questions/61815233/install-java-runtime-in-debian-based-docker-image
# - GATE installation is via izpack:
#   https://github.com/GateNLP/gate-core/blob/master/distro/src/main/izpack/install.xml
#   https://izpack.atlassian.net/wiki/spaces/IZPACK/pages/491674/Installer+Runtime+Options
#   https://izpack.atlassian.net/wiki/spaces/IZPACK/pages/42270722/Mixed+Installation+Mode+Using+Variable+Defaults
#   https://stackoverflow.com/questions/6519571/izpack-installer-options-auto
#   https://groups.google.com/forum/#!topic/izpack-user/ecp1U8CAOT8

RUN echo "- Updating package information..." \
    && apt-get update \
    && echo "- Installing operating system packages..." \
    && mkdir -p /usr/share/man/man1 /usr/share/man/man2 \
    && apt-get install -y --no-install-recommends \
        g++ \
        gcc \
        gdebi \
        git \
        wget \
        \
        wait-for-it \
        \
        antiword \
        freetds-bin \
        freetds-dev \
        graphviz \
        libgraphviz-dev \
        libmariadbclient-dev \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
        openjdk-11-jdk \
        openjdk-11-jre \
        poppler-utils \
        tdsodbc \
        unrtf \
        unixodbc-bin \
        unixodbc-dev \
    \
    && echo "- wkhtmltopdf: Fetching wkhtmltopdf with patched Qt (~14 Mb)..." \
    && wget -O /tmp/wkhtmltopdf.deb \
        https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.stretch_amd64.deb \
    && echo "- wkhtmltopdf: Installing wkhtmltopdf..." \
    && gdebi --non-interactive /tmp/wkhtmltopdf.deb \
    && echo "- wkhtmltopdf: Cleaning up..." \
    && rm /tmp/wkhtmltopdf.deb \
    \
    && echo "- GATE: fetching (~54 Mb)..." \
    && wget -O /tmp/gate-developer-8.6.1-installer.jar \
        https://github.com/GateNLP/gate-core/releases/download/v8.6.1/gate-developer-8.6.1-installer.jar \
    && echo "- GATE: installing..." \
    && java -jar /tmp/gate-developer-8.6.1-installer.jar \
        /crate/src/docker/dockerfiles/gate_auto_install.xml \
    && echo "- GATE: cleaning up..." \
    && rm /tmp/gate-developer-8.6.1-installer.jar \
    \
    && echo "- Creating Python 3 virtual environment..." \
    && python3 -m venv /crate/venv \
    && echo "- Upgrading pip within virtual environment..." \
    && /crate/venv/bin/python3 -m pip install --upgrade pip \
    && echo "- Installing CRATE and Python database drivers..." \
    && /crate/venv/bin/python3 -m pip install \
        /crate/src \
        django-mssql-backend==2.8.1 \
        mysqlclient==1.4.6 \
        psycopg2==2.8.5 \
        pyodbc==4.0.30 \
    \
    && echo "- Removing OS packages used only for the installation..." \
    && apt-get purge -y \
        g++ \
        gcc \
        gdebi \
        git \
        wget \
    && apt-get autoremove -y \
    && echo "- Cleaning up..." \
    && rm -rf /var/lib/apt/lists/* \
    && echo "- Done."

# TODO: SQL Server driver setup
# TODO: GATE pharmacotherapy
# TODO: other GATE apps
# TODO: NLPRP server


# -----------------------------------------------------------------------------
# EXPOSE: expose a port.
# -----------------------------------------------------------------------------
# We'll do this via docker-compose instead.

# EXPOSE 8000


# -----------------------------------------------------------------------------
# CMD: run the foreground task whose lifetime determines the container
# lifetime.
# -----------------------------------------------------------------------------
# Note: can be (and is) overridden by the "command" option in a docker-compose
# file.

# CMD ["/camcops/venv/bin/camcops_server" , "serve_gunicorn"]
# CMD ["/bin/bash"]

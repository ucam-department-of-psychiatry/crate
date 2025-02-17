# docker/dockerfiles/crate.Dockerfile
#
# Docker image that provides:
#
# - CRATE
# - database drivers
# - third-party text extraction tools
# - GATE
#
# Directory structure in container:
#
#   /crate              All CRATE code/binaries.
#       /cfg            Config files are mounted here.
#       /files          General file storage mounted here.
#       /gate           GATE program
#       /src            Source code for CRATE.
#       /static         Static files (Django STATIC_ROOT) mounted here.
#       /venv           Python 3 virtual environment.
#           /bin        Main CRATE executables live here.


# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------

FROM python:3.9-slim-bullseye AS crate-build-1-user
# This is a version of Debian 11 (see "cat /etc/debian_version").


# -----------------------------------------------------------------------------
# LABEL: metadata
# -----------------------------------------------------------------------------
# https://docs.docker.com/engine/reference/builder/#label


LABEL description="See https://crateanon.readthedocs.io/"
LABEL maintainer="Rudolf Cardinal <rudolf@pobox.com>"


# -----------------------------------------------------------------------------
# Permissions
# -----------------------------------------------------------------------------
# https://vsupalov.com/docker-shared-permissions/

ARG USER_ID
ARG GROUP_ID

RUN addgroup --gid $GROUP_ID crate

# The --no-log-init is necessary to prevent the image ballooning in size
# when USER_ID is large
# See https://github.com/moby/moby/issues/5419
RUN useradd --no-log-init --uid $USER_ID --gid $GROUP_ID crate

FROM crate-build-1-user AS crate-build-2-files

# -----------------------------------------------------------------------------
# ADD: files to copy
# -----------------------------------------------------------------------------
# - Syntax: ADD <host_file_spec> <container_dest_dir>
# - The host file spec is relative to the context (and can't go "above" it).
# - This docker file lives in the "docker/dockerfiles" directory within
#   the CRATE source, so we expect Docker to be told (externally -- see e.g.
#   the Docker Compose file) that the context is a higher directory.
#   That is the directory containing "setup.py" and therefore the installation
#   directory for our Python package.
# - So in short, here we refer to the context as ".".

ADD . /crate/src

FROM crate-build-2-files AS crate-build-3-environment

# -----------------------------------------------------------------------------
# COPY: can copy from other Docker images
# -----------------------------------------------------------------------------
# - https://docs.docker.com/engine/reference/builder/#copy
# - https://stackoverflow.com/questions/24958140/what-is-the-difference-between-the-copy-and-add-commands-in-a-dockerfile


# -----------------------------------------------------------------------------
# WORKDIR: Set working directory on container.
# -----------------------------------------------------------------------------
# Shouldn't really be necessary.

WORKDIR /crate


# -----------------------------------------------------------------------------
# RUN: run a command.
# -----------------------------------------------------------------------------
# - mmh3 needs g++ as well as gcc.
#
# - pdftotext is part of poppler-utils.
#
# - unixodbc-dev is required for the Python pyodbc package (or: missing sql.h).
#
# - Java for GATE (but default-jdk didn't work)...
#   ... in fact the problem is that you need
#   mkdir -p /usr/share/man/man1 /usr/share/man/man2
#   https://stackoverflow.com/questions/61815233/install-java-runtime-in-debian-based-docker-image
#
# - GATE installation is via izpack:
#   https://github.com/GateNLP/gate-core/blob/master/distro/src/main/izpack/install.xml
#   https://izpack.atlassian.net/wiki/spaces/IZPACK/pages/491674/Installer+Runtime+Options
#   https://izpack.atlassian.net/wiki/spaces/IZPACK/pages/42270722/Mixed+Installation+Mode+Using+Variable+Defaults
#   https://stackoverflow.com/questions/6519571/izpack-installer-options-auto
#   https://groups.google.com/forum/#!topic/izpack-user/ecp1U8CAOT8
#   ... the XML file determines the installation path.
#
# - Microsoft ODBC driver for SQL Server (Linux):
#   https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
#   - gnupg2 is required for the curl step.
#   - mssql-tools brings sqlcmd:
#     https://docs.microsoft.com/en-us/sql/tools/sqlcmd-utility
#
# - Testing KCL pharmacotherapy app:
#
#   export NLPPROGDIR=/crate/venv/lib/python3.9/site-packages/crate_anon/nlp_manager/compiled_nlp_classes/
#   export GATEDIR=/crate/gate
#   export GATE_PHARMACOTHERAPY_DIR=/crate/brc-gate-pharmacotherapy
#   export PLUGINFILE=/crate/src/crate_anon/nlp_manager/specimen_gate_plugin_file.ini
#   export TERMINATOR=END
#   java -classpath "${NLPPROGDIR}:${GATEDIR}/bin/gate.jar:${GATEDIR}/lib/*" -Dgate.home="${GATEDIR}" CrateGatePipeline --gate_app "${GATE_PHARMACOTHERAPY_DIR}/application.xgapp" --include_set Output --annotation Prescription --input_terminator "${TERMINATOR}" --output_terminator "${TERMINATOR}" --suppress_gate_stdout --pluginfile "${PLUGINFILE}"
#
# - For KConnect/Bio-YODIE:

#   - ant is required by plugins/compilePlugins.sh, from Bio-YODIE.
#   - see https://github.com/GateNLP/bio-yodie-resource-prep
#   - UMLS: separate licensing

ARG CRATE_ROOT=/crate
ARG CRATE_SRC=$CRATE_ROOT/src
ARG CRATE_VENV=$CRATE_ROOT/venv
ARG CRATE_VENV_BIN=$CRATE_VENV/bin
ARG CRATE_PACKAGE_ROOT=$CRATE_VENV/lib/python3.9/site-packages/crate_anon
ARG CRATE_GATE_PLUGIN_FILE=$CRATE_PACKAGE_ROOT/nlp_manager/specimen_gate_plugin_file.ini
ARG BIOYODIE_DIR=$CRATE_ROOT/bioyodie
ARG GATE_HOME=$CRATE_ROOT/gate
ARG GATE_VERSION
ARG KCL_LEWY_BODY_DIAGNOSIS_DIR=$CRATE_ROOT/kcl_lewy_body_dementia
ARG KCL_PHARMACOTHERAPY_PARENT_DIR=$CRATE_ROOT/kcl_pharmacotherapy
ARG KCL_PHARMACOTHERAPY_DIR=$KCL_PHARMACOTHERAPY_PARENT_DIR/brc-gate-pharmacotherapy
ARG TMPDIR=/tmp/crate_tmp

RUN mkdir -p "$TMPDIR"

FROM crate-build-3-environment AS crate-build-4-os-packages

RUN echo "===============================================================================" \
    && echo "OS packages, basic tools, and database drivers" \
    && echo "===============================================================================" \
    \
    && echo "- Updating package information..." \
    && apt-get update \
    && echo "- Installing operating system packages..." \
    && mkdir -p /usr/share/man/man1 /usr/share/man/man2 \
    && apt-get install -y --no-install-recommends \
        ca-certificates-java \
    && apt-get install -y --no-install-recommends \
        ant \
        curl \
        g++ \
        gcc \
        gdebi \
        git \
        gnupg2 \
        unzip \
        wget \
        \
        wait-for-it \
        \
        antiword \
        freetds-bin \
        freetds-dev \
        graphviz \
        libgraphviz-dev \
        libmariadb-dev \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
        openjdk-11-jdk \
        openjdk-11-jre \
        poppler-utils \
        tdsodbc \
        unrtf \
        wbritish

FROM crate-build-4-os-packages AS crate-build-5-odbc-packages

RUN echo "- Adding repositories..." \
    && echo "  * Microsoft ODBC driver for SQL Server" \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && echo "- Updating package information again..." \
    && apt-get update \
    \
    && echo "- Microsoft ODBC Driver for SQL Server (Linux)" \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql17 \
        mssql-tools \
        libgssapi-krb5-2 \
        unixodbc-dev=2.3.7 unixodbc=2.3.7 odbcinst1debian2=2.3.7 odbcinst=2.3.7 \
    && echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile \
    && echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc

FROM crate-build-5-odbc-packages AS crate-build-6-wkhtmltopdf

RUN echo "- wkhtmltopdf: Fetching wkhtmltopdf with patched Qt (~14 Mb)..." \
    && wget \
        --progress=dot:giga \
        -O "$TMPDIR/wkhtmltopdf.deb" \
        https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.stretch_amd64.deb \
    && echo "- wkhtmltopdf: Installing wkhtmltopdf..." \
    && gdebi --non-interactive "$TMPDIR/wkhtmltopdf.deb"

FROM crate-build-6-wkhtmltopdf AS crate-build-7-python-packages

RUN echo "===============================================================================" \
    && echo "CRATE" \
    && echo "===============================================================================" \
    && echo "- Creating Python 3 virtual environment..." \
    && python3 -m venv /crate/venv \
    && echo "- Upgrading pip within virtual environment..." \
    && "$CRATE_VENV_BIN/python3" -m pip install --upgrade pip \
    && echo "- Installing wheel within virtual environment..." \
    && "$CRATE_VENV_BIN/pip" install wheel==0.35.1 \
    && echo "- Installing CRATE (crate_anon, from source) and Python database drivers..." \
    && echo "  * MySQL [mysqlclient]" \
    && echo "  * PostgreSQL [psycopg2]" \
    && echo "  * SQL Server [mssql-django, pyodbc, Microsoft ODBC Driver for SQL Server (Linux) as above]" \
    && "$CRATE_VENV_BIN/python3" -m pip install \
        "$CRATE_SRC" \
        mssql-django==1.5 \
        mysqlclient==1.4.6 \
        psycopg2==2.8.5 \
        pyodbc==4.0.35 \
    && echo "- Installing remote debugger..." \
    && "$CRATE_VENV_BIN/python3" -m pip install remote-pdb

FROM crate-build-7-python-packages AS crate-build-8-nlp-tools

RUN echo "===============================================================================" \
    && echo "Third-party NLP tools" \
    && echo "===============================================================================" \
    && echo "- GATE..." \
    && $CRATE_VENV_BIN/crate_nlp_write_gate_auto_install_xml --filename $TMPDIR/gate_auto_install.xml --version $GATE_VERSION \
    && wget \
        --progress=dot:giga \
        -O "$TMPDIR/gate-installer.jar" \
        https://github.com/GateNLP/gate-core/releases/download/v$GATE_VERSION/gate-developer-$GATE_VERSION-installer.jar \
    && java -jar "$TMPDIR/gate-installer.jar" \
        "$TMPDIR/gate_auto_install.xml" \
    \
    && echo "- KCL BRC GATE Pharmacotherapy app..." \
    && wget \
        --progress=dot:giga \
        -O "$TMPDIR/brc-gate-pharmacotherapy.zip" \
        https://github.com/KHP-Informatics/brc-gate-pharmacotherapy/releases/download/1.1/brc-gate-pharmacotherapy.zip \
    && unzip "$TMPDIR/brc-gate-pharmacotherapy.zip" -d "$KCL_PHARMACOTHERAPY_PARENT_DIR" \
    \
    && echo "- Bio-YODIE..." \
    && git clone https://github.com/GateNLP/Bio-YODIE "$BIOYODIE_DIR" \
    && cd "$BIOYODIE_DIR" \
    && git pull --recurse-submodules=on-demand \
    && git submodule update --init --recursive \
    && plugins/compilePlugins.sh \
    \
    && echo "- KCL BRC GATE Lewy body dementia app..." \
    && git clone https://github.com/KHP-Informatics/brc-gate-LBD "$TMPDIR/kcl_lewy" \
    && unzip "$TMPDIR/kcl_lewy/Lewy_Body_Diagnosis.zip" -d "$KCL_LEWY_BODY_DIAGNOSIS_DIR" \
    && echo "- Compiling CRATE Java interfaces..." \
    && "$CRATE_VENV_BIN/crate_nlp_build_gate_java_interface" \
        --gatedir "$GATE_HOME"

FROM crate-build-8-nlp-tools AS crate-build-9-extra-nlp

RUN echo "===============================================================================" \
    && echo "Extra NLP steps" \
    && echo "===============================================================================" \
    && echo "- Running a GATE application to pre-download plugins..." \
    && java \
        -classpath "$CRATE_PACKAGE_ROOT/nlp_manager/gate_log_config:$CRATE_PACKAGE_ROOT/nlp_manager/compiled_nlp_classes:$GATE_HOME/lib/*" \
        -Dgate.home="$GATE_HOME" \
        CrateGatePipeline \
        --gate_app "$KCL_PHARMACOTHERAPY_DIR/application.xgapp" \
        --pluginfile "$CRATE_GATE_PLUGIN_FILE" \
        --suppress_gate_stdout \
        --launch_then_stop

FROM crate-build-9-extra-nlp AS crate-build-10-static-files

RUN echo "===============================================================================" \
    && echo "Creating static files directory" \
    && echo "===============================================================================" \
    && mkdir -p /crate/static \
    && chown -R crate:crate /crate/static

FROM crate-build-10-static-files AS crate-build-11-temp-files

RUN echo "===============================================================================" \
    && echo "Creating temp files directory" \
    && echo "===============================================================================" \
    && mkdir -p /crate/tmp \
    && chown -R crate:crate /crate/tmp

FROM crate-build-11-temp-files AS crate-build-12-cleanup

RUN echo "===============================================================================" \
    && echo "Cleanup" \
    && echo "===============================================================================" \
    && echo "- Removing OS packages used only for the installation..." \
    && echo "  (but keeping curl, git, unzip, wget)" \
    && apt-get purge -y \
        ant \
        g++ \
        gcc \
        gdebi \
        gnupg2 \
    && apt-get autoremove -y \
    && echo "- Cleaning up..." \
    && rm -rf "$TMPDIR" \
    && rm -rf /var/lib/apt/lists/* \
    && echo "- Done."

# -----------------------------------------------------------------------------
# ENV: set environment variables image-wide.
# -----------------------------------------------------------------------------

ENV PATH="${PATH}:/crate/venv/bin"

# -----------------------------------------------------------------------------
# EXPOSE: expose a port.
# -----------------------------------------------------------------------------
# We'll do this via docker-compose instead.

ENTRYPOINT ["/crate/src/docker/dockerfiles/docker-entrypoint.sh"]

# -----------------------------------------------------------------------------
# CMD: run the foreground task whose lifetime determines the container
# lifetime.
# -----------------------------------------------------------------------------
# Note: can be (and is) overridden by the "command" option in a docker-compose
# file.

# CMD ["/bin/bash"]

USER crate

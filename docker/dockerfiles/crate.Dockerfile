# docker/dockerfiles/crate.Dockerfile
#
# Directory structure in container:
#
#   /crate              All CRATE code/binaries.
#       /cfg            Config files are mounted here.
#       /src            Source code for CRATE.
#       /venv           Python 3 virtual environment.
#           /bin        Main CRATE executables live here.


# -----------------------------------------------------------------------------
# FROM: Base image
# -----------------------------------------------------------------------------

FROM python:3.6-slim-buster
# This is a version of Debian 10 (see "cat /etc/debian_version").


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
#   export NLPPROGDIR=/crate/venv/lib/python3.6/site-packages/crate_anon/nlp_manager/compiled_nlp_classes/
#   export GATEDIR=/crate/gate
#   export GATE_PHARMACOTHERAPY_DIR=/crate/brc-gate-pharmacotherapy
#   export PLUGINFILE=/crate/src/docs/source/nlp/specimen_gate_plugin_file.ini
#   export TERMINATOR=END
#   java -classpath "${NLPPROGDIR}:${GATEDIR}/bin/gate.jar:${GATEDIR}/lib/*" -Dgate.home="${GATEDIR}" CrateGatePipeline --gate_app "${GATE_PHARMACOTHERAPY_DIR}/application.xgapp" --include_set Output --annotation Prescription --input_terminator "${TERMINATOR}" --output_terminator "${TERMINATOR}" --suppress_gate_stdout --pluginfile "${PLUGINFILE}"

RUN echo "- Updating package information..." \
    && apt-get update \
    && echo "- Installing operating system packages..." \
    && mkdir -p /usr/share/man/man1 /usr/share/man/man2 \
    && apt-get install -y --no-install-recommends \
        curl \
        g++ \
        gcc \
        gdebi \
        git \
        gnupg2 \
        wget \
        zip \
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
    \
    && echo "- Adding repositories..." \
    && echo "  * Microsoft ODBC driver for SQL Server" \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && echo "- Updating package information again..." \
    && apt-get update \
    \
    && echo "- Microsoft ODBC Driver for SQL Server (Linux)" \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql17 \
        mssql-tools \
        libgssapi-krb5-2 \
        unixodbc unixodbc-dev \
    && echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile \
    && echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc \
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
    && wget -O /tmp/gate-installer.jar \
        https://github.com/GateNLP/gate-core/releases/download/v8.6.1/gate-developer-8.6.1-installer.jar \
    && echo "- GATE: installing..." \
    && java -jar /tmp/gate-installer.jar \
        /crate/src/docker/dockerfiles/gate_auto_install.xml \
    && echo "- GATE: cleaning up..." \
    && rm /tmp/gate-installer.jar \
    \
    && echo "- KCL BRC GATE Pharmacotherapy app..." \
    && wget -O /tmp/brc-gate-pharmacotherapy.zip \
        https://github.com/KHP-Informatics/brc-gate-pharmacotherapy/releases/download/1.1/brc-gate-pharmacotherapy.zip \
    && unzip /tmp/brc-gate-pharmacotherapy.zip -d /crate \
    && rm /tmp/brc-gate-pharmacotherapy.zip \
    \
    && echo "- Creating Python 3 virtual environment..." \
    && python3 -m venv /crate/venv \
    && echo "- Upgrading pip within virtual environment..." \
    && /crate/venv/bin/python3 -m pip install --upgrade pip \
    && echo "- Installing CRATE and Python database drivers..." \
    && echo "  * MySQL [mysqlclient]" \
    && echo "  * PostgreSQL [psycopg2]" \
    && echo "  * SQL Server [django-mssql-backend, pyodbc, Microsoft ODBC Driver for SQL Server (Linux) as above]" \
    && /crate/venv/bin/python3 -m pip install \
        /crate/src \
        django-mssql-backend==2.8.1 \
        mysqlclient==1.4.6 \
        psycopg2==2.8.5 \
        pyodbc==4.0.30 \
    && echo "- Compiling CRATE Java interfaces..." \
    && /crate/venv/bin/crate_nlp_build_gate_java_interface \
        --gatedir /crate/gate \
    \
    && echo "- Removing OS packages used only for the installation..." \
    && apt-get purge -y \
        curl \
        g++ \
        gcc \
        gdebi \
        git \
        gnupg2 \
        wget \
        zip \
    && apt-get autoremove -y \
    && echo "- Cleaning up..." \
    && rm -rf /var/lib/apt/lists/* \
    && echo "- Done."

# TODO: NLPRP server (via docker-compose.yaml)


# -----------------------------------------------------------------------------
# EXPOSE: expose a port.
# -----------------------------------------------------------------------------
# We'll do this via docker-compose instead.


# -----------------------------------------------------------------------------
# CMD: run the foreground task whose lifetime determines the container
# lifetime.
# -----------------------------------------------------------------------------
# Note: can be (and is) overridden by the "command" option in a docker-compose
# file.

# CMD ["/bin/bash"]

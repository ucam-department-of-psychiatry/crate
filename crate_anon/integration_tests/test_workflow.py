#!/usr/bin/env python

"""
crate_anon/tests/test_workflow.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

Test workflows including database access across several database engines. For
development purposes.

Network inspection:

.. code-block:: bash

    docker network ls

    docker network inspect crate_docker_testnet

    docker container ls --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" -a
    # PORTS: e.g.
    #   0.0.0.0:1433->1433/tcp, :::1433->1433/tcp
    # shows mapping from container -> host.
    # - "0.0.0.0" is "from any interface" in IPv4;
    # - "::" means "consecutive blocks of zeroes" in IPv6.
    # https://www.cloudbees.com/blog/docker-expose-port-what-it-means-and-what-it-doesnt-mean#what-is-a-port  # noqa: E501

    docker port <CONTAINER>
    # e.g.:
    #   1433/tcp -> 0.0.0.0:1433
    #   1433/tcp -> [::]:1433
    # ... here mapping host -> container.

    docker inspect <CONTAINER>

Debugging MySQL connection failures:

- Using ``--host=127.0.0.1`` means that you will see "Can't connect to MySQL
  server on ...", meaning network failure, if there is one. However, if you use
  ``--host=localhost``, you just see "Access denied..." which is the same error
  message as for a wrong password etc. (i.e. that error message is a bit
  unhelpful).

"""

import argparse
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
import logging
from os.path import abspath, dirname, join
import tempfile
import time
from typing import Dict, List, Tuple

from cardinal_pythonlib.fileops import mkdir_p
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from python_on_whales import docker

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.anonymise.make_demo_database import mk_demo_database
from crate_anon.anonymise.researcher_report import (
    mk_researcher_report_pdf,
    ResearcherReportConfig,
)
from crate_anon.common.argparse_assist import (
    RawDescriptionArgumentDefaultsRichHelpFormatter,
)
from crate_anon.version import CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

THIS_SCRIPT_DIR = dirname(abspath(__file__))
CONTEXT = THIS_SCRIPT_DIR

MYSQL = "mysql"
SQLSERVER = "sqlserver"
POSTGRESQL = "postgres"
ALL = "all"

ENGINES = [ALL, MYSQL, SQLSERVER, POSTGRESQL]

LOCAL_IP_ADDRESS = "127.0.0.1"
# With MySQL, if you use "localhost", it tries a socket connection; you need
# 127.0.0.1 for a TCP/IP connection. Other engines don't care.
DEFAULT_SQLSERVER_PORT = 1433
DEFAULT_MYSQL_PORT = 3306
DEFAULT_POSTGRES_PORT = 5432

DEFAULT_TIMEOUT_S = 60

# Different network to the CRATE Docker containers
# See docker/dockerfiles/docker-compose.yaml
DOCKER_NETWORK = "crate_test_net"

CONTAINER_ENGINE_PREFIX = "crate_test_container_engine"
CONTAINER_DBSHELL = "crate_test_container_dbshell"
CONTAINER_BASH = "crate_test_container_bash"

# The following defaults should match the Dockerfile(s):
DB_SRC: str = "sourcedb"
DB_ANON: str = "anondb"
DB_SECRET: str = "secretdb"
DB_NLP: str = "nlpdb"
DB_CRATE: str = "cratedb"
DB_TEST: str = "testdb"
DB_ROOT_PASSWORD: str = "9@dVM7?v5U4q"  # random, e.g. https://www.lastpass.com
DB_PRIVUSER_USER: str = "administrator"
DB_PRIVUSER_PASSWORD: str = "8z3?I84@mvBX"
DB_RESEARCHER_USER: str = "researcher"
DB_RESEARCHER_PASSWORD: str = "G6f@V3?oc3Yb"
DB_TEST_USER: str = "tester"
DB_TEST_PASSWORD: str = "Qcig@cuW?myo"
# Postgres has an additional layer... database/schema/table.
PG_DB_IDENT = "identdb"
PG_DB_DEIDENT = "deidentdb"

DOCKER_BUILD_ARGS = {
    # Corresponding to ARG variables in the Dockerfile(s).
    # Database names
    "DB_SRC": DB_SRC,
    "DB_ANON": DB_ANON,
    "DB_SECRET": DB_SECRET,
    "DB_NLP": DB_NLP,
    "DB_CRATE": DB_CRATE,
    "DB_TEST": DB_TEST,
    "PG_DB_IDENT": PG_DB_IDENT,
    "PG_DB_DEIDENT": PG_DB_DEIDENT,
    # Usernames/passwords
    "DB_ROOT_PASSWORD": DB_ROOT_PASSWORD,
    "DB_PRIVUSER_USER": DB_PRIVUSER_USER,
    "DB_PRIVUSER_PASSWORD": DB_PRIVUSER_PASSWORD,
    "DB_RESEARCHER_USER": DB_RESEARCHER_USER,
    "DB_RESEARCHER_PASSWORD": DB_RESEARCHER_PASSWORD,
    "DB_TEST_USER": DB_TEST_USER,
    "DB_TEST_PASSWORD": DB_TEST_PASSWORD,
    # NB this is an INSECURE method; see
    # https://docs.docker.com/engine/reference/builder/#arg. But this is just
    # a quick demo with no actual sensitive information.
}


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class EngineInfo:
    name: str
    docker_container_name: str
    dockerfile: str
    tag: str
    docker_port: int
    sqla_dialect: str
    python_driver: str = None
    envvars: Dict[str, str] = None
    dbshellcmd: List[str] = None
    dbshellenv: Dict[str, str] = None
    sqla_url_option_suffix: str = ""
    both_db_schema: bool = False

    def sqlalchemy_url(
        self,
        dbname: str,
        user: str,
        password: str,
        port: int,
        ip_addr: str = LOCAL_IP_ADDRESS,
    ) -> str:
        """
        SQLAlchemy URL for a given database.
        """
        dialect = self.sqla_dialect
        if self.python_driver:
            dialect += "+" + self.python_driver
        return (
            f"{dialect}://{user}:{password}@{ip_addr}:{port}/"
            f"{dbname}{self.sqla_url_option_suffix}"
        )

    @staticmethod
    def _user_pw(privileged: bool = False) -> Tuple[str, str]:
        if privileged:
            return DB_PRIVUSER_USER, DB_PRIVUSER_PASSWORD
        return DB_RESEARCHER_USER, DB_RESEARCHER_PASSWORD

    def sqlalchemy_url_src(
        self,
        port: int,
        ip: str = LOCAL_IP_ADDRESS,
    ) -> str:
        user, password = self._user_pw(privileged=True)
        dbname = PG_DB_IDENT if self.both_db_schema else DB_SRC
        return self.sqlalchemy_url(
            dbname=dbname,
            user=user,
            password=password,
            ip_addr=ip,
            port=port,
        )

    def sqlalchemy_url_anon(
        self,
        port: int,
        ip: str = LOCAL_IP_ADDRESS,
        privileged: bool = False,
    ) -> str:
        user, password = self._user_pw(privileged)
        dbname = PG_DB_DEIDENT if self.both_db_schema else DB_ANON
        return self.sqlalchemy_url(
            dbname=dbname,
            user=user,
            password=password,
            ip_addr=ip,
            port=port,
        )

    def sqlalchemy_url_nlp(
        self,
        port: int,
        ip: str = LOCAL_IP_ADDRESS,
        privileged: bool = False,
    ) -> str:
        user, password = self._user_pw(privileged)
        dbname = PG_DB_DEIDENT if self.both_db_schema else DB_NLP
        return self.sqlalchemy_url(
            dbname=dbname,
            user=user,
            password=password,
            ip_addr=ip,
            port=port,
        )


# =============================================================================
# Engine definitions
# =============================================================================

ENGINEINFO = {
    SQLSERVER: EngineInfo(
        name="Microsoft SQL Server",
        docker_container_name=f"{CONTAINER_ENGINE_PREFIX}_sqlserver",
        dockerfile=join(THIS_SCRIPT_DIR, "sqlserver.Dockerfile"),
        tag="crate_test_sqlserver",
        docker_port=DEFAULT_SQLSERVER_PORT,
        sqla_dialect="mssql",
        # python_driver="pyodbc",
        python_driver="pymssql",
        dbshellcmd=[
            # https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-connect-database-engine?view=sql-server-ver16  # noqa: E501
            "sqlcmd",
            "-C",  # Allow self-signed certificate
            "-S",
            f"{CONTAINER_ENGINE_PREFIX}_sqlserver,{DEFAULT_SQLSERVER_PORT}",
            "-U",
            "sa",  # SQLServer root user
            "-P",
            DB_ROOT_PASSWORD,
        ],
        # ... relies on the network alias
        envvars={"ACCEPT_EULA": "Y"},
    ),
    MYSQL: EngineInfo(
        name="MySQL (MariaDB)",
        docker_container_name=f"{CONTAINER_ENGINE_PREFIX}_mysql",
        dockerfile=join(THIS_SCRIPT_DIR, "mysql.Dockerfile"),
        tag="crate_test_mysql",
        docker_port=DEFAULT_MYSQL_PORT,
        sqla_dialect="mysql",
        python_driver="mysqldb",  # = mysqlclient
        sqla_url_option_suffix="?charset=utf8",
        dbshellcmd=[
            "mysql",
            f"--host={CONTAINER_ENGINE_PREFIX}_mysql",
            f"--port={DEFAULT_MYSQL_PORT}",
            "--user=root",  # MySQL root user
            f"--password={DB_ROOT_PASSWORD}",
        ],
    ),
    POSTGRESQL: EngineInfo(
        name="PostgreSQL (Postgres)",
        docker_container_name=f"{CONTAINER_ENGINE_PREFIX}_postgres",
        dockerfile=join(THIS_SCRIPT_DIR, "postgres.Dockerfile"),
        tag="crate_test_postgres",
        docker_port=DEFAULT_POSTGRES_PORT,
        sqla_dialect="postgresql",
        # Python driver usually psycopg2, but it doesn't need specifying.
        dbshellenv={"PGPASSWORD": DB_ROOT_PASSWORD},
        dbshellcmd=[
            "psql",
            f"--host={CONTAINER_ENGINE_PREFIX}_postgres",
            f"--port={DEFAULT_POSTGRES_PORT}",
            "--username=postgres",  # PostgreSQL root user
        ],
        both_db_schema=True,
    ),
}


# =============================================================================
# Manage Docker containers
# =============================================================================


def makenet() -> None:
    """
    Set up a Docker network for all our containers.
    """
    if docker.network.list(filters={"name": DOCKER_NETWORK}):
        log.info(f"Docker network already exists: {DOCKER_NETWORK}")
        return

    log.info(f"Creating Docker network: {DOCKER_NETWORK}")
    docker.network.create(DOCKER_NETWORK, driver="bridge")


def build(engine_info: EngineInfo) -> None:
    """
    Build a database engine's Docker container.
    """
    log.info(f"Building Docker container for engine: {engine_info.name}")
    docker.build(
        file=engine_info.dockerfile,
        tags=[engine_info.tag],
        context_path=CONTEXT,
        build_args=DOCKER_BUILD_ARGS,
    )


def launch_bash(engine_info: EngineInfo) -> None:
    """
    Run Bash in a database engine's container.
    """
    log.info(f"Launching Bash for Docker container: {engine_info.name}")
    docker.run(
        engine_info.tag,
        command=["bash"],
        interactive=True,
        name=CONTAINER_BASH,
        networks=[DOCKER_NETWORK],
        remove=True,
        tty=True,
    )


def start_engine(
    engine_info: EngineInfo, host_port: int, timeout_s=DEFAULT_TIMEOUT_S
) -> None:
    """
    Start the database engine's container, so it provides database services.
    """
    envvars = engine_info.envvars.copy() if engine_info.envvars else {}
    log.info(f"Starting database engine, via host port {host_port}")
    docker.run(
        engine_info.tag,
        envs=envvars,
        publish=[(host_port, engine_info.docker_port)],
        networks=[DOCKER_NETWORK],
        name=engine_info.docker_container_name,
        detach=True,
    )

    ip_address = get_crate_container_engine_ip_address(engine_info)
    wait_for_databases_to_be_created(engine_info, 60)
    log.info(
        f"Database engine started on {ip_address}:{engine_info.docker_port}"
    )


def wait_for_databases_to_be_created(
    engine_info: EngineInfo, timeout_s: float
) -> None:
    start_time = time.time()

    while time.time() - start_time < timeout_s:
        logs = docker.logs(engine_info.docker_container_name)
        if ">>> Databases created. READY." in logs:
            return

        time.sleep(1)

    log.error(docker.logs(engine_info.docker_container_name))
    raise TimeoutError("Gave up waiting for the databases to be created.")


def get_crate_container_engine_ip_address(engine_info: EngineInfo) -> str:
    container = docker.container.inspect(engine_info.docker_container_name)
    network_settings = container.network_settings

    return network_settings.networks[DOCKER_NETWORK].ip_address


def start_dbshell(engine_info: EngineInfo) -> None:
    """
    Start a database shell within the Docker container.
    """
    envvars = engine_info.envvars.copy() if engine_info.envvars else {}
    if engine_info.dbshellenv:
        envvars.update(engine_info.dbshellenv)
    docker.run(
        engine_info.tag,
        command=engine_info.dbshellcmd,
        envs=envvars,
        interactive=True,
        networks=[DOCKER_NETWORK],
        name=CONTAINER_DBSHELL,
        remove=True,
        tty=True,
    )


# =============================================================================
# Test workflow
# =============================================================================


def test_researcher_report(
    tempdir: str,
    db_url: str,
    db_name: str,
    anonconfig: Config = None,
    echo: bool = False,
) -> None:
    """
    Test researcher reports.
    """
    rrc = ResearcherReportConfig(
        anonconfig=anonconfig,
        output_filename=join(tempdir, "researcher_report.pdf"),
        db_url=db_url,
        db_name=db_name,
        echo=echo,
    )
    mk_researcher_report_pdf(rrc)


def test_crate_workflow(
    engine_info: EngineInfo, port: int, tempdir: str, echo: bool = False
) -> None:
    log.info(f"Temporary directory: {tempdir}")
    url_src = engine_info.sqlalchemy_url_src(port=port)
    url_anon_priv = engine_info.sqlalchemy_url_anon(port=port, privileged=True)
    url_anon_res = engine_info.sqlalchemy_url_anon(port=port, privileged=False)
    url_nlp_priv = engine_info.sqlalchemy_url_nlp(port=port, privileged=True)
    url_nlp_res = engine_info.sqlalchemy_url_nlp(port=port, privileged=False)
    _ = DatabaseHolder(
        DB_SRC,
        url_src,
        with_session=True,
        reflect=True,
    )
    _ = DatabaseHolder(
        DB_ANON,
        url_anon_priv,
        with_session=True,
        reflect=True,
    )
    _ = DatabaseHolder(
        DB_ANON,
        url_anon_res,
        with_session=True,
        reflect=True,
    )
    _ = DatabaseHolder(
        DB_NLP,
        url_nlp_priv,
        with_session=True,
        reflect=True,
    )
    _ = DatabaseHolder(
        DB_NLP,
        url_nlp_res,
        with_session=True,
        reflect=True,
    )
    log.info("Successfully opened databases.")

    # -------------------------------------------------------------------------
    # Create databases
    # -------------------------------------------------------------------------

    log.info("Building source database.")
    mk_demo_database(
        url=url_src, n_patients=100, notes_per_patient=20, words_per_note=100
    )

    # -------------------------------------------------------------------------
    # Not yet done
    # -------------------------------------------------------------------------

    log.warning("Not yet implemented: anonymisation tests")
    log.warning("Not yet implemented: NLP tests")

    # -------------------------------------------------------------------------
    # Researcher reports
    # -------------------------------------------------------------------------

    log.info("Running researcher reports.")
    anonconfig = None  # basic report only; todo: could improve
    test_researcher_report(
        tempdir=tempdir,
        db_url=url_src,
        db_name=DB_SRC,
        anonconfig=anonconfig,
        echo=echo,
    )


# =============================================================================
# Temporary directory management
# =============================================================================


def mktempdir(tempdir: str = None) -> AbstractContextManager:
    """
    1. The operation of Python's "with" statement is explained at:
    https://docs.python.org/3/reference/compound_stmts.html#with.

    2. The "@contextlib.contextmanager" decorator changes a function that
    yields a value into something that can be used by the "with" statement,
    by adding "__enter__()" and "__exit__()" methods.

    3. The "nullcontext" function provides a stand-in for an optional context
    manager:
    https://docs.python.org/3/library/contextlib.html#contextlib.nullcontext.

    Here, we want to use a named directory if the user has provided one (which
    will be created if required but which will not be deleted afterwards), or
    otherwise a temporary directory that is deleted when the context ends.

    Because tempfile.TemporaryDirectory() provides a context manager directly,
    we should return (not be) a context manager.
    """
    if not tempdir:
        return tempfile.TemporaryDirectory()
    mkdir_p(tempdir)
    return nullcontext(tempdir)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    cmd_bash = "bash"
    cmd_startengine = "startengine"
    cmd_dbshell = "dbshell"
    cmd_makedb = "makedb"
    cmd_testcrate = "testcrate"

    parser = argparse.ArgumentParser(
        description=f"Test CRATE workflows including across different "
        f"database engines (via Docker). Intended to be run on a machine that "
        f"can start Docker containers, i.e. natively. "
        f"({CRATE_VERSION_PRETTY})",
        formatter_class=RawDescriptionArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "action",
        type=str,
        choices=[
            cmd_bash,
            cmd_startengine,
            cmd_dbshell,
            cmd_makedb,
            cmd_testcrate,
        ],
        help=f"""Command to perform.
(1) {cmd_bash!r}: Run a Bash shell in the Docker container for a given
database, without starting the database itself.

(2) {cmd_startengine!r}: Start the database proper. Do this in a SEPARATE
process.

(3) {cmd_dbshell!r}: Launch the database engine's command-line tool, within the
Docker container. Assumes the engine container is ALREADY RUNNING in a separate
process (see {cmd_startengine!r}).

(4) {cmd_makedb!r}: Create test databases.

(5) {cmd_testcrate!r}: Test CRATE against the database engine. Assumes the
engine container is ALREADY RUNNING in a separate process (see
{cmd_startengine!r}).
""",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=ENGINES,
        default=SQLSERVER,
        help="Database engine to test",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="Number of seconds to wait for the database engine to be created",
    )
    parser.add_argument(
        "--hostport",
        type=int,
        default=None,
        help="Host port to use for the database engine (default is to use the "
        "same as the Docker port)",
    )
    parser.add_argument(
        "--tempdir",
        type=str,
        help="Named directory to use as a temporary directory. If specified, "
        "this directory will be created (if necessary), used, and then left "
        "for your inspection. If not specified, a transient temporary "
        "directory will be used.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    parser.add_argument("--echo", action="store_true", help="Echo some SQL")
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    main_only_quicksetup_rootlogger(level=loglevel)

    makenet()
    engines_to_use = ENGINES if args.engine == ALL else [args.engine]
    for engine in engines_to_use:
        engine_info = ENGINEINFO[engine]
        host_port = args.hostport or engine_info.docker_port
        with mktempdir(args.tempdir) as tempdir:
            if args.action == cmd_bash:
                build(engine_info)
                launch_bash(engine_info)
            elif args.action == cmd_startengine:
                build(engine_info)
                start_engine(
                    engine_info, host_port=host_port, timeout_s=args.timeout
                )
            elif args.action == cmd_dbshell:
                start_dbshell(engine_info)
            elif args.action == cmd_makedb:
                raise NotImplementedError
            elif args.action == cmd_testcrate:
                test_crate_workflow(
                    engine_info,
                    port=host_port,
                    tempdir=tempdir,
                    echo=args.echo,
                )
            else:
                raise RuntimeError("bug")


if __name__ == "__main__":
    main()

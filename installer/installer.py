#!/usr/bin/env python

"""
installer/installer.py

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

Installs CRATE running under Docker with demonstration databases. Bootstrapped
from ``installer.sh``. Note that the full CRATE Python environment is NOT
available.

"""

from argparse import ArgumentParser
import collections
import os
from pathlib import Path
from platform import uname
import re
import secrets
import shutil
import string
import sys
from tempfile import NamedTemporaryFile
import textwrap
from typing import (
    Callable,
    Dict,
    Iterable,
    NoReturn,
    TextIO,
    Tuple,
    Type,
    Union,
)
import urllib.parse

# See installer-requirements.txt
from prompt_toolkit import HTML, print_formatted_text, prompt
from prompt_toolkit.completion import PathCompleter, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator, ValidationError

# noinspection PyUnresolvedReferences
from python_on_whales import docker, DockerClient, DockerException
from python_on_whales.components.container.cli_wrapper import Container

from semantic_version import Version

# Python Prompt Toolkit has basic support for text entry / yes-no / alert
# dialogs but unfortunately there are a couple of features lacking:
#
# Completion does not display:
# https://github.com/prompt-toolkit/python-prompt-toolkit/issues/715
#
# No way of specifying a default:
# https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1544
#
# So for now, just use basic prompts.
#
# An alternative library is Urwid (https://urwid.org/) but that leaves a
# lot of work for the programmer (See file browser example:
# https://github.com/urwid/urwid/blob/master/examples/browse.py


# =============================================================================
# Constants
# =============================================================================

MINIMUM_DOCKER_COMPOSE_VERSION = Version("2.0.0")
EXIT_FAILURE = 1


class HostPath:
    """
    Directories and filenames as seen from the host OS.
    """

    INSTALLER_DIR = os.path.dirname(os.path.realpath(__file__))
    PROJECT_ROOT = os.path.join(INSTALLER_DIR, "..")
    DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")
    DOCKERFILES_DIR = os.path.join(DOCKER_DIR, "dockerfiles")

    HOME_DIR = os.path.expanduser("~")
    CRATE_DIR = os.path.join(HOME_DIR, "crate")
    DEFAULT_HOST_CRATE_CONFIG_DIR = os.path.join(CRATE_DIR, "config")
    DEFAULT_HOST_CRATE_FILES_DIR = os.path.join(CRATE_DIR, "files")
    DEFAULT_HOST_CRATE_STATIC_DIR = os.path.join(CRATE_DIR, "static")
    DEFAULT_HOST_BIOYODIE_DIR = os.path.join(CRATE_DIR, "bioyodie_resources")

    ENVVAR_SAVE_FILE = "set_crate_docker_host_envvars"


class DockerPath:
    """
    Directories and filenames as seen from the Docker containers.
    """

    BASH = "/bin/bash"

    ROOT_DIR = "/crate"

    CONFIG_DIR = os.path.join(ROOT_DIR, "cfg")
    ARCHIVE_TEMPLATE_DIR = os.path.join(CONFIG_DIR, "archive_templates")
    ARCHIVE_ATTACHMENT_DIR = os.path.join(CONFIG_DIR, "archive_attachments")
    ARCHIVE_STATIC_DIR = os.path.join(CONFIG_DIR, "static")

    TMP_DIR = os.path.join(ROOT_DIR, "tmp")
    ARCHIVE_TEMPLATE_CACHE_DIR = os.path.join(
        TMP_DIR, "archive_template_cache"
    )
    PRIVATE_FILE_STORAGE_ROOT = os.path.join(TMP_DIR, "files")

    VENV_DIR = os.path.join(ROOT_DIR, "venv")
    CRATE_INSTALL_DIR = os.path.join(
        VENV_DIR, "lib", "python3.8", "site-packages"
    )


class DockerComposeServices:
    """
    Subset of services named in ``docker/dockerfiles/docker-compose-*.yaml``.
    """

    CRATE_DB = "crate_db"
    CRATE_SERVER = "crate_server"
    CRATE_WORKERS = "crate_workers"
    FLOWER = "flower"
    RABBITMQ = "rabbitmq"
    RESEARCH_DB = "research_db"
    SECRET_DB = "secret_db"
    SOURCE_DB = "source_db"


class EnvVar:
    PASSWORD_SUFFIX = "PASSWORD"


class DockerEnvVar(EnvVar):
    """
    Environment variables governing the Docker setup.

    See: docker/dockerfiles/docker-compose.yaml
         docker/dockerfiles/docker-compose-*.yaml
         docker/dockerfiles/.env

    Any others go in InstallerEnvVar
    """

    PREFIX = "CRATE_DOCKER"

    CONFIG_HOST_DIR = f"{PREFIX}_CONFIG_HOST_DIR"
    CRATE_ANON_CONFIG = f"{PREFIX}_CRATE_ANON_CONFIG"
    CRATE_CHERRYPY_ARGS = f"{PREFIX}_CRATE_CHERRYPY_ARGS"
    CRATE_WAIT_FOR = f"{PREFIX}_CRATE_WAIT_FOR"
    CRATEWEB_CONFIG_FILENAME = f"{PREFIX}_CRATEWEB_CONFIG_FILENAME"
    CRATEWEB_HOST_PORT = f"{PREFIX}_CRATEWEB_HOST_PORT"
    CRATEWEB_SUPERUSER_EMAIL = f"{PREFIX}_CRATEWEB_SUPERUSER_EMAIL"
    CRATEWEB_SUPERUSER_PASSWORD = (
        f"{PREFIX}_CRATEWEB_SUPERUSER_{EnvVar.PASSWORD_SUFFIX}"
    )
    CRATEWEB_SUPERUSER_USERNAME = f"{PREFIX}_CRATEWEB_SUPERUSER_USERNAME"
    FILES_HOST_DIR = f"{PREFIX}_FILES_HOST_DIR"
    GATE_BIOYODIE_RESOURCES_HOST_DIR = (
        f"{PREFIX}_GATE_BIOYODIE_RESOURCES_HOST_DIR"
    )
    INSTALL_USER_ID = f"{PREFIX}_INSTALL_USER_ID"

    CRATE_DB_DATABASE_NAME = f"{PREFIX}_CRATE_DB_DATABASE_NAME"
    CRATE_DB_HOST_PORT = f"{PREFIX}_CRATE_DB_HOST_PORT"
    CRATE_DB_ROOT_PASSWORD = f"{PREFIX}_CRATE_DB_ROOT_{EnvVar.PASSWORD_SUFFIX}"
    CRATE_DB_USER_NAME = f"{PREFIX}_CRATE_DB_USER_NAME"
    CRATE_DB_USER_PASSWORD = f"{PREFIX}_CRATE_DB_USER_{EnvVar.PASSWORD_SUFFIX}"

    ODBC_USER_CONFIG = f"{PREFIX}_ODBC_USER_CONFIG"

    RESEARCH_DATABASE_NAME = f"{PREFIX}_RESEARCH_DATABASE_NAME"
    RESEARCH_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )
    RESEARCH_DATABASE_USER_NAME = f"{PREFIX}_RESEARCH_DATABASE_USER_NAME"
    RESEARCH_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )

    SECRET_DATABASE_NAME = f"{PREFIX}_SECRET_DATABASE_NAME"
    SECRET_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )
    SECRET_DATABASE_USER_NAME = f"{PREFIX}_SECRET_DATABASE_USER_NAME"
    SECRET_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )

    SOURCE_DATABASE_NAME = f"{PREFIX}_SOURCE_DATABASE_NAME"
    SOURCE_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )
    SOURCE_DATABASE_USER_NAME = f"{PREFIX}_SOURCE_DATABASE_USER_NAME"
    SOURCE_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"  # noqa
    )
    STATIC_HOST_DIR = f"{PREFIX}_STATIC_HOST_DIR"


class InstallerEnvVar(EnvVar):
    PREFIX = "CRATE_INSTALLER"

    CRATE_DB_ENGINE = f"{PREFIX}_CRATE_DB_ENGINE"
    CRATE_DB_SERVER = f"{PREFIX}_CRATE_DB_SERVER"
    CRATE_DB_PORT = f"{PREFIX}_CRATE_DB_PORT"
    CRATEWEB_SSL_CERTIFICATE = f"{PREFIX}_CRATEWEB_SSL_CERTIFICATE"
    CRATEWEB_SSL_PRIVATE_KEY = f"{PREFIX}_CRATEWEB_SSL_PRIVATE_KEY"
    CRATEWEB_USE_HTTPS = f"{PREFIX}_CRATEWEB_USE_HTTPS"
    CREATE_CRATE_DB_CONTAINER = f"{PREFIX}_CREATE_CRATE_DB_CONTAINER"
    CREATE_DEMO_DB_CONTAINERS = f"{PREFIX}_CREATE_DEMO_DB_CONTAINERS"

    RESEARCH_DATABASE_ENGINE = f"{PREFIX}_RESEARCH_DATABASE_ENGINE"
    RESEARCH_DATABASE_HOST = f"{PREFIX}_RESEARCH_DATABASE_HOST"
    RESEARCH_DATABASE_PORT = f"{PREFIX}_RESEARCH_DATABASE_PORT"

    SECRET_DATABASE_ENGINE = f"{PREFIX}_SECRET_DATABASE_ENGINE"
    SECRET_DATABASE_HOST = f"{PREFIX}_SECRET_DATABASE_HOST"
    SECRET_DATABASE_PORT = f"{PREFIX}_SECRET_DATABASE_PORT"

    SOURCE_DATABASE_ENGINE = f"{PREFIX}_SOURCE_DATABASE_ENGINE"
    SOURCE_DATABASE_HOST = f"{PREFIX}_SOURCE_DATABASE_HOST"
    SOURCE_DATABASE_PORT = f"{PREFIX}_SOURCE_DATABASE_PORT"


# =============================================================================
# Database Engines
# =============================================================================
class DatabaseEngine(
    collections.namedtuple(
        "DatabaseEngine", ["description", "sqlalchemy", "django"]
    )
):
    pass


# =============================================================================
# Validators
# =============================================================================


class NotEmptyValidator(Validator):
    def validate(self, document: Document) -> None:
        if not document.text:
            raise ValidationError(message="Must provide an answer")


class YesNoValidator(Validator):
    def validate(self, document: Document) -> None:
        text = document.text

        if text.lower() not in ("y", "n"):
            raise ValidationError(message="Please answer 'y' or 'n'")


class FileValidator(Validator):
    def validate(self, document: Document) -> None:
        filename = document.text

        if not os.path.isfile(os.path.expanduser(filename)):
            raise ValidationError(message=f"{filename!r} is not a valid file")


class EmailValidator(Validator):
    _SIMPLE_EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def validate(self, document: Document) -> None:
        email = document.text
        if self._SIMPLE_EMAIL_REGEX.match(email) is None:
            raise ValidationError(message=f"{email!r} is not a valid e-mail")


class ChoiceValidator(Validator):
    def __init__(self, choices: Iterable[str], *args, **kwargs) -> None:
        self.choices = choices
        super().__init__(*args, **kwargs)

    def validate(self, document: Document) -> None:
        if document.text not in self.choices:
            choices_str = ", ".join(self.choices)
            raise ValidationError(message=f"choose one of {choices_str}")


# =============================================================================
# Colours
# =============================================================================
class Colours:
    # https://en.wikipedia.org/wiki/Solarized
    # Background tones (dark theme)
    BASE03 = "#002b36"
    BASE02 = "#073642"
    # Content tones
    BASE01 = "#586e75"
    BASE00 = "#657b83"
    BASE0 = "#839496"
    BASE1 = "#93a1a1"
    # Background tones (light theme)
    BASE2 = "#eee8d5"
    BASE3 = "#fdf6e3"
    # Accent tones
    YELLOW = "#b58900"
    ORANGE = "#cb4b16"
    RED = "#dc322f"
    MAGENTA = "#d33682"
    VIOLET = "#6c71c4"
    BLUE = "#268bd2"
    CYAN = "#2aa198"
    GREEN = "#859900"


# =============================================================================
# Installer base class
# =============================================================================


class Installer:
    def __init__(
        self,
        verbose: bool = False,
        update: bool = False,
    ) -> None:
        self._docker = None
        self._engines = None
        self.verbose = verbose
        self.update = update

        self.title = "CRATE Setup"
        self.intro_style = Style.from_dict(
            {
                "span": f"{Colours.BLUE}",
            }
        )
        prompt_dict = {"span": f"{Colours.CYAN}"}

        self.prompt_style = Style.from_dict(prompt_dict)
        self.info_style = Style.from_dict(
            {
                "span": f"{Colours.VIOLET}",
            }
        )
        self.error_style = Style.from_dict(
            {
                "span": f"{Colours.RED}",
            }
        )
        self.envvar_style = Style.from_dict(
            {
                "span": f"{Colours.GREEN}",
            }
        )
        choice_dict = prompt_dict.copy()
        choice_dict.update(name=f"{Colours.ORANGE}")
        self.choice_style = Style.from_dict(choice_dict)

    @property
    def engines(self) -> Dict[str, DatabaseEngine]:
        if self._engines is None:
            self._engines = self.get_database_engines()

        return self._engines

    def get_database_engines(self) -> Dict[str, DatabaseEngine]:
        return {
            "mssql": DatabaseEngine(
                "Microsoft SQL Server",
                "mssql+pyodbc",
                "mssql",
            ),
            "mysql": DatabaseEngine(
                "MySQL or MariaDB",
                "mysql+mysqldb",
                "django.db.backends.mysql",
            ),
            "oracle": DatabaseEngine(
                "Oracle",
                "oracle+cxoracle",
                "django.db.backends.oracle",
            ),
            "postgresql": DatabaseEngine(
                "PostgreSQL",
                "postgresql+psycopg2",
                "django.db.backends.postgresql",
            ),
        }

    @property
    def docker(self) -> DockerClient:
        if self._docker is None:
            compose_files = ["docker-compose.yaml"]

            if self.should_create_crate_db_container():
                compose_files.append("docker-compose-crate-db.yaml")

            if self.should_create_demo_containers():
                compose_files.extend(
                    [
                        "docker-compose-research-db.yaml",
                        "docker-compose-secret-db.yaml",
                        "docker-compose-source-db.yaml",
                    ]
                )

            self._docker = DockerClient(compose_files=compose_files)

        return self._docker

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def install(self) -> None:
        self.start_message()
        self.check_setup()
        self.configure()
        self.write_environment_variables()

        self.build_crate_image()

        # At this point the containers get created
        self.create_local_settings()
        self.create_anon_config()
        if self.use_https():
            self.copy_ssl_files()
        self.create_or_update_crate_database()
        self.collect_static()
        self.populate()
        self.create_superuser()
        self.start()

        if self.should_create_demo_containers():
            self.create_demo_data()
        self.create_data_dictionary()
        if self.should_create_demo_containers():
            self.anonymise_demo_data()

        self.report_status()

    def build_crate_image(self) -> None:
        if self.update:
            self.info("Updating existing CRATE installation")
        os.chdir(HostPath.DOCKERFILES_DIR)
        self.docker.compose.build(
            services=[
                DockerComposeServices.CRATE_SERVER,
                DockerComposeServices.CRATE_WORKERS,
                DockerComposeServices.FLOWER,
            ],
            cache=not self.update,
        )

    def start(self) -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        self.docker.compose.up(detach=True)

    def stop(self) -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        self.docker.compose.down(volumes=True)

    def run_shell_in_crate_container(self, as_root: bool = False) -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)

        user = "root" if as_root else None

        self.docker.compose.execute(
            DockerComposeServices.CRATE_SERVER,
            [DockerPath.BASH],
            user=user,
        )

    def run_crate_command_and_output_to_file(
        self, crate_command: str, filename: str
    ) -> None:
        stdout = self.run_crate_command(crate_command)
        with open(filename, "w") as f:
            f.write(stdout)

    def run_crate_command(
        self, crate_command: str
    ) -> Union[str, Container, Iterable[Tuple[str, bytes]]]:
        # Run a command in a new instance of the crate_workers container.
        # This goes through docker-entrypoint.sh so no need to source the
        # virtualenv or call /bin/bash
        os.chdir(HostPath.DOCKERFILES_DIR)
        return self.docker.compose.run(
            DockerComposeServices.CRATE_WORKERS,
            remove=True,
            tty=False,
            command=[crate_command],
        )

    def exec_crate_command(self, crate_command: str) -> None:
        # Run a command in the existing instance of the crate_server
        # container. This does not go through entrypoint.sh so we have to
        # source the virtualenv and call /bin/bash
        venv_command = f'""source /crate/venv/bin/activate; {crate_command}""'

        os.chdir(HostPath.DOCKERFILES_DIR)

        self.docker.compose.execute(
            DockerComposeServices.CRATE_SERVER,
            [DockerPath.BASH, "-c", venv_command],
        )

    # -------------------------------------------------------------------------
    # Info messages
    # -------------------------------------------------------------------------

    @staticmethod
    def report(text: str, style: Style) -> None:
        print_formatted_text(HTML(f"<span>{text}</span>"), style=style)

    def start_message(self) -> None:
        self.report("CRATE Installer", self.intro_style)

    def info(self, text: str) -> None:
        self.report(text, self.info_style)

    def envvar_info(self, text: str) -> None:
        if not self.verbose:
            return
        self.report(text, self.envvar_style)

    def error(self, text: str) -> None:
        self.report(text, self.error_style)

    def fail(self, text: str) -> NoReturn:
        self.error(text)
        sys.exit(EXIT_FAILURE)

    # -------------------------------------------------------------------------
    # Installation
    # -------------------------------------------------------------------------

    def check_setup(self) -> None:
        # We call docker here, not self.docker because we haven't yet
        # worked out which compose files we'll be using.
        info = docker.info()
        if info.id is None:
            self.fail(
                "Could not connect to Docker. Check that Docker is "
                "running and your user is in the 'docker' group."
            )

        try:
            # python_on_whales doesn't support --short or --format so we do
            # some parsing
            version_string = docker.compose.version().split()[-1].lstrip("v")
        except DockerException:
            self.fail(
                "It looks like you don't have Docker Compose installed. "
                "Please install Docker Compose v2 or greater. See "
                "https://github.com/docker/compose; "
                "https://docs.docker.com/compose/cli-command/"
            )

        version = Version(version_string)
        if version < MINIMUM_DOCKER_COMPOSE_VERSION:
            self.fail(
                f"The version of Docker Compose ({version}) is too old. "
                f"Please install v{MINIMUM_DOCKER_COMPOSE_VERSION} or greater."
            )

    def configure(self) -> None:
        try:
            self.configure_user()
            self.configure_config_files()
            self.configure_files_dir()
            self.configure_static_dir()
            self.create_directories()
            self.write_odbc_config()
            self.configure_crateweb()
            self.configure_crate_db()
            self.configure_anon_dbs()
            self.configure_django()
            self.configure_cherrypy()
            self.configure_wait_for()
        except (KeyboardInterrupt, EOFError):
            # The user pressed CTRL-C or CTRL-D
            self.error("Installation aborted")
            self.write_environment_variables()
            sys.exit(EXIT_FAILURE)

    def configure_user(self) -> None:
        self.setenv(
            DockerEnvVar.INSTALL_USER_ID, self.get_docker_install_user_id
        )

    def configure_config_files(self) -> None:
        self.setenv(
            DockerEnvVar.CONFIG_HOST_DIR, self.get_docker_config_host_dir
        )
        self.setenv(
            DockerEnvVar.GATE_BIOYODIE_RESOURCES_HOST_DIR,
            self.get_docker_gate_bioyodie_resources_host_dir,
        )
        self.setenv(
            DockerEnvVar.CRATEWEB_CONFIG_FILENAME, "crateweb_local_settings.py"
        )
        self.setenv(DockerEnvVar.CRATE_ANON_CONFIG, "crate_anon_config.ini")
        self.setenv(DockerEnvVar.ODBC_USER_CONFIG, "odbc_user.ini")

    def configure_files_dir(self) -> None:
        self.setenv(
            DockerEnvVar.FILES_HOST_DIR, self.get_docker_files_host_dir
        )

    def configure_static_dir(self) -> None:
        self.setenv(
            DockerEnvVar.STATIC_HOST_DIR, self.get_docker_static_host_dir
        )

    def configure_crateweb(self) -> None:
        self.setenv(
            DockerEnvVar.CRATEWEB_HOST_PORT, self.get_docker_crateweb_host_port
        )
        self.setenv(
            InstallerEnvVar.CRATEWEB_USE_HTTPS,
            self.get_docker_crateweb_use_https,
        )
        if self.use_https():
            self.setenv(
                InstallerEnvVar.CRATEWEB_SSL_CERTIFICATE,
                self.get_crateweb_ssl_certificate,
            )
            self.setenv(
                InstallerEnvVar.CRATEWEB_SSL_PRIVATE_KEY,
                self.get_crateweb_ssl_private_key,
            )

    def configure_crate_db(self) -> None:
        self.setenv(
            InstallerEnvVar.CREATE_CRATE_DB_CONTAINER,
            self.get_create_crate_db_container,
        )

        if self.should_create_crate_db_container():
            return self.configure_crate_db_container()

        self.configure_external_crate_db()

    def configure_crate_db_container(self) -> None:
        self.setenv(InstallerEnvVar.CRATE_DB_ENGINE, "mysql")
        self.setenv(InstallerEnvVar.CRATE_DB_SERVER, "crate_db")
        self.setenv(InstallerEnvVar.CRATE_DB_PORT, "3306")
        self.setenv(
            DockerEnvVar.CRATE_DB_ROOT_PASSWORD,
            self.get_docker_crate_db_root_password,
            obscure=True,
        )
        self.setenv(DockerEnvVar.CRATE_DB_DATABASE_NAME, "crate_web_db")
        self.setenv(DockerEnvVar.CRATE_DB_USER_NAME, "crate_web_user")
        self.setenv(
            DockerEnvVar.CRATE_DB_USER_PASSWORD,
            self.get_docker_crate_db_user_password,
            obscure=True,
        )
        self.setenv(
            DockerEnvVar.CRATE_DB_HOST_PORT,
            self.get_docker_crate_db_host_port,
        )

    def configure_external_crate_db(self) -> None:
        self.info(
            "Enter the details of the external database used for the "
            "CRATE web application"
        )
        self.external_db_instructions()

        self.setenv(
            InstallerEnvVar.CRATE_DB_ENGINE,
            self.get_external_db_engine,
        )
        self.setenv(
            InstallerEnvVar.CRATE_DB_SERVER,
            self.get_external_db_server,
        )
        self.setenv(
            InstallerEnvVar.CRATE_DB_PORT,
            self.get_external_db_port,
        )
        self.setenv(
            DockerEnvVar.CRATE_DB_DATABASE_NAME,
            self.get_external_db_database_name,
        )
        self.setenv(
            DockerEnvVar.CRATE_DB_USER_NAME,
            self.get_external_db_user_name,
        )
        self.setenv(
            DockerEnvVar.CRATE_DB_USER_PASSWORD,
            self.get_external_db_user_password,
            obscure=True,
        )

    def configure_anon_dbs(self) -> None:
        self.setenv(
            InstallerEnvVar.CREATE_DEMO_DB_CONTAINERS,
            self.get_create_demo_containers,
        )

        if self.should_create_demo_containers():
            self.configure_demo_source_db()
            self.configure_demo_research_db()
            self.configure_demo_secret_db()
            return

        self.configure_external_source_db()
        self.configure_external_research_db()
        self.configure_external_secret_db()

    def configure_demo_research_db(self) -> None:
        self.setenv(InstallerEnvVar.RESEARCH_DATABASE_ENGINE, "mysql")
        self.setenv(InstallerEnvVar.RESEARCH_DATABASE_HOST, "research_db")
        self.setenv(InstallerEnvVar.RESEARCH_DATABASE_PORT, "3306")
        self.setenv(
            DockerEnvVar.RESEARCH_DATABASE_ROOT_PASSWORD,
            "research",
            obscure=True,
        )
        self.setenv(DockerEnvVar.RESEARCH_DATABASE_NAME, "research")
        self.setenv(DockerEnvVar.RESEARCH_DATABASE_USER_NAME, "research")
        self.setenv(
            DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD,
            "research",
            obscure=True,
        )

    def configure_demo_secret_db(self) -> None:
        self.setenv(InstallerEnvVar.SECRET_DATABASE_ENGINE, "mysql")
        self.setenv(InstallerEnvVar.SECRET_DATABASE_HOST, "secret_db")
        self.setenv(InstallerEnvVar.SECRET_DATABASE_PORT, "3306")
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_ROOT_PASSWORD, "secret", obscure=True
        )
        self.setenv(DockerEnvVar.SECRET_DATABASE_NAME, "secret")
        self.setenv(DockerEnvVar.SECRET_DATABASE_USER_NAME, "secret")
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_USER_PASSWORD, "secret", obscure=True
        )

    def configure_demo_source_db(self) -> None:
        self.setenv(InstallerEnvVar.SOURCE_DATABASE_ENGINE, "mysql")
        self.setenv(InstallerEnvVar.SOURCE_DATABASE_HOST, "source_db")
        self.setenv(InstallerEnvVar.SOURCE_DATABASE_PORT, "3306")
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_ROOT_PASSWORD, "source", obscure=True
        )
        self.setenv(DockerEnvVar.SOURCE_DATABASE_NAME, "source")
        self.setenv(DockerEnvVar.SOURCE_DATABASE_USER_NAME, "source")
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD, "source", obscure=True
        )

    def configure_external_research_db(self) -> None:
        self.info(
            "Enter the details of an external research database. This is "
            "where the anonymised data will be stored. More "
            "research databases can be added by manually editing the "
            "configuration files generated by CRATE after installation."
        )
        self.external_db_instructions()

        self.setenv(
            InstallerEnvVar.RESEARCH_DATABASE_ENGINE,
            self.get_external_db_engine,
        )
        self.setenv(
            InstallerEnvVar.RESEARCH_DATABASE_HOST,
            self.get_external_db_server,
        )
        self.setenv(
            InstallerEnvVar.RESEARCH_DATABASE_PORT,
            self.get_external_db_port,
        )
        self.setenv(
            DockerEnvVar.RESEARCH_DATABASE_NAME,
            self.get_external_db_database_name,
        )
        self.setenv(
            DockerEnvVar.RESEARCH_DATABASE_USER_NAME,
            self.get_external_db_user_name,
        )
        self.setenv(
            DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD,
            self.get_external_db_user_password,
            obscure=True,
        )

    def configure_external_secret_db(self) -> None:
        self.info(
            "Enter the details of an external secret administrative database. "
            "This stores information like Patient ID to Research ID mapping. "
            "More secret databases can be added by manually editing the "
            "configuration files generated by CRATE after installation. There "
            "should be one secret administrative database for every research "
            "database."
        )
        self.external_db_instructions()

        self.setenv(
            InstallerEnvVar.SECRET_DATABASE_ENGINE,
            self.get_external_db_engine,
        )
        self.setenv(
            InstallerEnvVar.SECRET_DATABASE_HOST,
            self.get_external_db_server,
        )
        self.setenv(
            InstallerEnvVar.SECRET_DATABASE_PORT,
            self.get_external_db_port,
        )
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_NAME,
            self.get_external_db_database_name,
        )
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_USER_NAME,
            self.get_external_db_user_name,
        )
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_USER_PASSWORD,
            self.get_external_db_user_password,
            obscure=True,
        )

    def configure_external_source_db(self) -> None:
        self.info(
            "Enter the details of an external source database. This "
            "contains the data to be anonymised. More "
            "source databases can be added by manually editing the "
            "configuration files generated by CRATE after installation."
        )
        self.external_db_instructions()

        self.setenv(
            InstallerEnvVar.SOURCE_DATABASE_ENGINE,
            self.get_external_db_engine,
        )
        self.setenv(
            InstallerEnvVar.SOURCE_DATABASE_HOST,
            self.get_external_db_server,
        )
        self.setenv(
            InstallerEnvVar.SOURCE_DATABASE_PORT,
            self.get_external_db_port,
        )
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_NAME,
            self.get_external_db_database_name,
        )
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_USER_NAME,
            self.get_external_db_user_name,
        )
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD,
            self.get_external_db_user_password,
            obscure=True,
        )

    def external_db_instructions(self) -> None:
        self.info(
            "CRATE will attempt to connect to the external database during "
            "installation."
        )
        self.info("Before continuing:")
        self.info(
            "1. The database server must allow remote connections "
            "(e.g. for MySQL bind-address = 0.0.0.0 in mysqld.cnf)."
        )
        self.info(
            "2. The database must exist. For Microsoft SQL Server, the DSN "
            f"should be defined in {self.odbc_config_full_path()}."
        )
        self.info(
            "3. A user must exist with remote access to the database "
            "(for MySQL use mysql_native_password authentication)."
        )

    def configure_django(self) -> None:
        self.setenv(
            DockerEnvVar.CRATEWEB_SUPERUSER_USERNAME,
            self.get_docker_crateweb_superuser_username,
        )
        self.setenv(
            DockerEnvVar.CRATEWEB_SUPERUSER_PASSWORD,
            self.get_docker_crateweb_superuser_password,
            obscure=True,
        )
        self.setenv(
            DockerEnvVar.CRATEWEB_SUPERUSER_EMAIL,
            self.get_docker_crateweb_superuser_email,
        )

    def configure_cherrypy(self) -> None:
        # - Re host 0.0.0.0:
        #   https://nickjanetakis.com/blog/docker-tip-54-fixing-connection-reset-by-peer-or-similar-errors
        cherrypy_args = ["--host 0.0.0.0", "--port 8000"]

        if self.use_https():
            cherrypy_args.extend(
                [
                    f"--ssl_certificate {DockerPath.CONFIG_DIR}/crate.crt",
                    f"--ssl_private_key {DockerPath.CONFIG_DIR}/crate.key",
                ]
            )
        self.setenv(DockerEnvVar.CRATE_CHERRYPY_ARGS, " ".join(cherrypy_args))

    def configure_wait_for(self) -> None:
        wait_for = [
            f"{DockerComposeServices.RABBITMQ}:5672",
        ]

        if self.should_create_crate_db_container():
            wait_for.append(f"{DockerComposeServices.CRATE_DB}:3306")
        #
        if self.should_create_demo_containers():
            wait_for.extend(
                [
                    f"{DockerComposeServices.RESEARCH_DB}:3306",
                    f"{DockerComposeServices.SECRET_DB}:3306",
                    f"{DockerComposeServices.SOURCE_DB}:3306",
                ]
            )

        self.setenv(DockerEnvVar.CRATE_WAIT_FOR, " ".join(wait_for))

    @staticmethod
    def create_directories() -> None:
        crate_config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        Path(crate_config_dir).mkdir(parents=True, exist_ok=True)

        crate_files_dir = os.environ.get(DockerEnvVar.FILES_HOST_DIR)
        Path(crate_files_dir).mkdir(parents=True, exist_ok=True)

        crate_static_dir = os.environ.get(DockerEnvVar.STATIC_HOST_DIR)
        Path(crate_static_dir).mkdir(parents=True, exist_ok=True)

        bioyodie_resources_dir = os.environ.get(
            DockerEnvVar.GATE_BIOYODIE_RESOURCES_HOST_DIR
        )
        Path(bioyodie_resources_dir).mkdir(parents=True, exist_ok=True)

    def write_odbc_config(self) -> None:
        demo_config = r"""# Example ODBC DSN definition

# [put_name_of_dsn_here]
# Driver = ODBC Driver 17 for SQL Server
# Description  = Put description here
# SERVER       = host.docker.internal
# USER         = username
# Password     = password
# Database     = name_of_database

# [put_name_of_second_dsn_here]
# ...
"""  # noqa: E501

        config = self.odbc_config_full_path()
        if not os.path.exists(config):
            self.info(f"Writing sample ODBC config to: {config}")
            with open(config, "w") as f:
                f.write(demo_config)

    def create_local_settings(self) -> None:
        settings = self.local_settings_full_path()
        if not os.path.exists(settings):
            self.info(f"Creating {settings}")
            Path(settings).touch()
            self.run_crate_command_and_output_to_file(
                "crate_print_demo_crateweb_config --leave_placeholders",
                settings,
            )
        self.configure_local_settings()

    def configure_local_settings(self) -> None:
        replace_dict = {
            "archive_attachment_dir": DockerPath.ARCHIVE_ATTACHMENT_DIR,
            "archive_static_dir": DockerPath.ARCHIVE_STATIC_DIR,
            "archive_template_cache_dir": DockerPath.ARCHIVE_TEMPLATE_CACHE_DIR,  # noqa: E501
            "archive_template_dir": DockerPath.ARCHIVE_TEMPLATE_DIR,
            "broker_url": "amqp://rabbitmq:5672",
            "crate_db_engine": self.engines[
                os.getenv(InstallerEnvVar.CRATE_DB_ENGINE)
            ].django,
            "crate_db_name": os.getenv(DockerEnvVar.CRATE_DB_DATABASE_NAME),
            "crate_db_host": os.getenv(InstallerEnvVar.CRATE_DB_SERVER),
            "crate_db_password": os.getenv(
                DockerEnvVar.CRATE_DB_USER_PASSWORD
            ),
            "crate_db_port": os.getenv(InstallerEnvVar.CRATE_DB_PORT),
            "crate_db_user": os.getenv(DockerEnvVar.CRATE_DB_USER_NAME),
            "crate_https": str(self.use_https()),
            "crate_install_dir": DockerPath.CRATE_INSTALL_DIR,
            "dest_db_engine": self.engines[
                os.getenv(InstallerEnvVar.RESEARCH_DATABASE_ENGINE)
            ].django,
            "dest_db_host": os.getenv(InstallerEnvVar.RESEARCH_DATABASE_HOST),
            "dest_db_port": os.getenv(InstallerEnvVar.RESEARCH_DATABASE_PORT),
            "dest_db_name": os.getenv(DockerEnvVar.RESEARCH_DATABASE_NAME),
            "dest_db_user": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_NAME
            ),
            "dest_db_password": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD
            ),
            "django_site_root_absolute_url": "http://mymachine.mydomain",
            "force_script_name": self.get_crate_server_path(),
            "pdf_logo_abs_url": "file:///crate/cfg/crate_logo.png",
            "private_file_storage_root": DockerPath.PRIVATE_FILE_STORAGE_ROOT,
            "rdi1_name": "research",
            "rdi1_description": "Demo research database",
            "rdi1_database": "",
            "rdi1_schema": "research",
            "rdi1_pid_psuedo_field": "pid",
            "rdi1_mpid_pseudo_field": "mpid",
            "rdi1_trid_field": "trid",
            "rdi1_rid_field": "brcid",
            "rdi1_rid_family": "1",
            "rdi1_mrid_table": "patients",
            "rdi1_mrid_field": "nhshash",
            "rdi1_pid_description": "Patient ID",
            "rdi1_mpid_description": "Master patient ID",
            "rdi1_rid_description": "Research ID",
            "rdi1_mrid_description": "Master research ID",
            "rdi1_trid_description": "Transient research ID",
            "rdi1_secret_lookup_db": "secret_1",
            "rdi1_date_fields_by_table": "",
            "rdi1_default_date_fields": "",
            "rdi1_update_date_field": "_when_fetched_utc",
            "research_db_for_contact_lookup": "research",
            "secret_key": secrets.token_urlsafe(),
            "secret_db1_engine": self.engines[
                os.getenv(InstallerEnvVar.SECRET_DATABASE_ENGINE)
            ].django,
            "secret_db1_host": os.getenv(InstallerEnvVar.SECRET_DATABASE_HOST),
            "secret_db1_port": os.getenv(InstallerEnvVar.SECRET_DATABASE_PORT),
            "secret_db1_name": os.getenv(DockerEnvVar.SECRET_DATABASE_NAME),
            "secret_db1_user": os.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_NAME
            ),
            "secret_db1_password": os.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_PASSWORD
            ),
        }

        self.search_replace_file(
            self.local_settings_full_path(),
            replace_dict,
        )

    def create_anon_config(self) -> None:
        config = self.anon_config_full_path()
        if not os.path.exists(config):
            self.info(f"Creating {config}")
            Path(config).touch()
            self.run_crate_command_and_output_to_file(
                "crate_anon_demo_config --leave_placeholders", config
            )
        self.configure_anon_config()

    def configure_anon_config(self) -> None:
        replace_dict = {
            "data_dictionary_filename": self.get_data_dictionary_docker_filename(),  # noqa: E501
            "per_table_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "master_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "change_detection_encryption_phrase": self.get_hmac_md5_key(),
            "dest_db_url": self.get_sqlalchemy_url(
                os.getenv(InstallerEnvVar.RESEARCH_DATABASE_ENGINE),
                os.getenv(DockerEnvVar.RESEARCH_DATABASE_USER_NAME),
                os.getenv(DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD),
                os.getenv(InstallerEnvVar.RESEARCH_DATABASE_HOST),
                os.getenv(InstallerEnvVar.RESEARCH_DATABASE_PORT),
                os.getenv(DockerEnvVar.RESEARCH_DATABASE_NAME),
            ),
            "admin_db_url": self.get_sqlalchemy_url(
                os.getenv(InstallerEnvVar.SECRET_DATABASE_ENGINE),
                os.getenv(DockerEnvVar.SECRET_DATABASE_USER_NAME),
                os.getenv(DockerEnvVar.SECRET_DATABASE_USER_PASSWORD),
                os.getenv(InstallerEnvVar.SECRET_DATABASE_HOST),
                os.getenv(InstallerEnvVar.SECRET_DATABASE_PORT),
                os.getenv(DockerEnvVar.SECRET_DATABASE_NAME),
            ),
            "source_db1_url": self.get_sqlalchemy_url(
                os.getenv(InstallerEnvVar.SOURCE_DATABASE_ENGINE),
                os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_NAME),
                os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD),
                os.getenv(InstallerEnvVar.SOURCE_DATABASE_HOST),
                os.getenv(InstallerEnvVar.SOURCE_DATABASE_PORT),
                os.getenv(DockerEnvVar.SOURCE_DATABASE_NAME),
            ),
            "source_db1_ddgen_include_fields": "Note.note",
            "source_db1_ddgen_scrubsrc_patient_fields": self.format_multiline(
                ("forename", "surname")
            ),
        }

        self.search_replace_file(self.anon_config_full_path(), replace_dict)

    @staticmethod
    def copy_ssl_files() -> None:
        config_dir = os.getenv(DockerEnvVar.CONFIG_HOST_DIR)

        cert_dest = os.path.join(config_dir, "crate.crt")
        key_dest = os.path.join(config_dir, "crate.key")

        shutil.copy(
            os.getenv(InstallerEnvVar.CRATEWEB_SSL_CERTIFICATE), cert_dest
        )
        shutil.copy(
            os.getenv(InstallerEnvVar.CRATEWEB_SSL_PRIVATE_KEY), key_dest
        )

    def create_or_update_crate_database(self) -> None:
        self.run_crate_command("crate_django_manage migrate")

    def collect_static(self) -> None:
        self.run_crate_command("crate_django_manage collectstatic --no-input")

    def populate(self) -> None:
        self.run_crate_command("crate_django_manage populate")

    def create_superuser(self) -> None:
        # Will either create a superuser or update an existing one
        # with the given username
        self.run_crate_command("crate_django_manage ensuresuperuser")

    def create_demo_data(self) -> None:
        engine = os.getenv(InstallerEnvVar.SOURCE_DATABASE_ENGINE)
        user = os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_NAME)
        password = os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD)
        host = os.getenv(InstallerEnvVar.SOURCE_DATABASE_HOST)
        port = os.getenv(InstallerEnvVar.SOURCE_DATABASE_PORT)
        name = os.getenv(DockerEnvVar.SOURCE_DATABASE_NAME)
        url = self.get_sqlalchemy_url(engine, user, password, host, port, name)
        self.run_crate_command(f"crate_make_demo_database {url}")

    def create_data_dictionary(self) -> None:
        data_dictionary = self.get_data_dictionary_host_filename()
        self.run_crate_command_and_output_to_file(
            "crate_anon_draft_dd", data_dictionary
        )

    def anonymise_demo_data(self) -> None:
        self.run_crate_command("crate_anonymise --full")

    def report_status(self) -> None:
        localhost_url = self.get_crate_server_localhost_url()
        self.info(f"The CRATE application is running at {localhost_url}")

    # -------------------------------------------------------------------------
    # Fetching information from environment variables or statically
    # -------------------------------------------------------------------------

    @staticmethod
    def get_docker_install_user_id() -> str:
        return str(os.geteuid())

    @staticmethod
    def get_hmac_md5_key() -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16))

    @staticmethod
    def local_settings_full_path() -> str:
        return os.path.join(
            os.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            os.getenv(DockerEnvVar.CRATEWEB_CONFIG_FILENAME),
        )

    @staticmethod
    def anon_config_full_path() -> str:
        return os.path.join(
            os.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            os.getenv(DockerEnvVar.CRATE_ANON_CONFIG),
        )

    @staticmethod
    def odbc_config_full_path() -> str:
        return os.path.join(
            os.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            os.getenv(DockerEnvVar.ODBC_USER_CONFIG),
        )

    @staticmethod
    def get_data_dictionary_host_filename() -> str:
        return os.path.join(
            os.getenv(DockerEnvVar.CONFIG_HOST_DIR), "data_dictionary.tsv"
        )

    @staticmethod
    def get_data_dictionary_docker_filename() -> str:
        return os.path.join(DockerPath.CONFIG_DIR, "data_dictionary.tsv")

    def get_sqlalchemy_url(
        self,
        engine: str,
        user: str,
        password: str,
        host: str,
        port: str,
        name: str,
    ) -> str:
        path = ""
        query = ""
        scheme = self.engines[engine].sqlalchemy
        netloc = f"{user}:{password}@"
        if host:
            netloc = f"{netloc}{host}"
            if port:
                netloc = f"{netloc}:{port}"
            path = name
        else:
            # DSN
            netloc = f"{netloc}{name}"

        if engine == "mysql":
            # Possibly not necessary and potentially wrong if, say utf8mb4
            # For now, leave it to the user to fix in the config file.
            query = "charset=utf8"

        params = fragment = None
        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def get_crate_server_localhost_url(self) -> str:
        scheme = self.get_crate_server_scheme()
        port = self.get_crate_server_port_from_host()
        netloc = f"localhost:{port}"
        path = self.get_crate_server_path()
        params = query = fragment = None
        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def get_crate_server_scheme(self) -> str:
        if self.use_https():
            return "https"
        return "http"

    @staticmethod
    def use_https() -> bool:
        return os.getenv(InstallerEnvVar.CRATEWEB_USE_HTTPS) == "1"

    def should_create_crate_db_container(self) -> bool:
        create = os.getenv(InstallerEnvVar.CREATE_CRATE_DB_CONTAINER)
        if create is None:
            self.fail(
                f"{InstallerEnvVar.CREATE_CRATE_DB_CONTAINER} "
                "should be set to 0 or 1"
            )

        return create == "1"

    def should_create_demo_containers(self) -> bool:
        create = os.getenv(InstallerEnvVar.CREATE_DEMO_DB_CONTAINERS)
        if create is None:
            self.fail(
                f"{InstallerEnvVar.CREATE_DEMO_DB_CONTAINERS} "
                "should be set to 0 or 1"
            )

        return create == "1"

    @staticmethod
    def get_crate_server_path() -> str:
        return "/crate"

    def get_crate_server_ip_address(self) -> str:
        container = self.docker.container.inspect("crate_crate_server")
        network_settings = container.network_settings

        return network_settings.networks["crate_crateanon_network"].ip_address

    @staticmethod
    def get_crate_server_port_from_host() -> str:
        return os.getenv(DockerEnvVar.CRATEWEB_HOST_PORT)

    # -------------------------------------------------------------------------
    # Fetching information from the user
    # -------------------------------------------------------------------------

    def get_docker_config_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the host directory where CRATE will store its "
            "configuration:",
            default=HostPath.DEFAULT_HOST_CRATE_CONFIG_DIR,
        )

    def get_docker_files_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the host directory for general CRATE file storage",
            default=HostPath.DEFAULT_HOST_CRATE_FILES_DIR,
        )

    def get_docker_static_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the host directory where CRATE will store static files "
            "for the CRATE web application:",
            default=HostPath.DEFAULT_HOST_CRATE_STATIC_DIR,
        )

    def get_docker_gate_bioyodie_resources_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the host directory where CRATE will store Bio-YODIE "
            "resources:",
            default=HostPath.DEFAULT_HOST_BIOYODIE_DIR,
        )

    def get_docker_crateweb_host_port(self) -> str:
        return self.get_user_input(
            (
                "Enter the port where the CRATE web app will appear on the "
                "host:"
            ),
            default="8000",
        )

    def get_docker_crateweb_use_https(self) -> str:
        return self.get_user_boolean(
            "Access the CRATE web app directly over HTTPS? "
            "Answer 'n' if HTTPS traffic will be routed via a web server "
            "(e.g. Apache) (y/n)"
        )

    def get_crateweb_ssl_certificate(self) -> str:
        return self.get_user_file("Select the SSL certificate file:")

    def get_crateweb_ssl_private_key(self) -> str:
        return self.get_user_file("Select the SSL private key file:")

    def get_create_crate_db_container(self) -> bool:
        return self.get_user_boolean(
            "Create a MySQL database for the CRATE web application? "
            "Answer 'n' to use an external database (y/n)"
        )

    def get_docker_crate_db_root_password(self) -> str:
        return self.get_user_password(
            "Enter a new MySQL root password for CRATE's internal database:"
        )

    def get_docker_crate_db_user_password(self) -> str:
        username = os.environ[DockerEnvVar.CRATE_DB_USER_NAME]
        return self.get_user_password(
            f"Enter a new password for the internal MySQL user ({username!r}) "
            f"that CRATE will create:"
        )

    def get_docker_crate_db_host_port(self) -> str:
        return self.get_user_input(
            (
                "Enter the port where CRATE's internal MySQL database will "
                "appear on the host:"
            ),
            default="43306",
        )

    def get_create_demo_containers(self) -> bool:
        return self.get_user_boolean(
            "Create demo databases for anonymisation? "
            "Answer 'n' to set up external databases (y/n)?"
        )

    def get_docker_crateweb_superuser_username(self) -> str:
        return self.get_user_input(
            "Enter the user name for the CRATE web app administrator:",
            default="admin",
        )

    def get_docker_crateweb_superuser_password(self) -> str:
        return self.get_user_password(
            "Enter the password for the CRATE web app administrator:"
        )

    def get_docker_crateweb_superuser_email(self) -> str:
        return self.get_user_email(
            "Enter the email address for the CRATE web app administrator:"
        )

    def get_external_db_engine(self) -> str:
        choice_dict = {
            name: e.description for (name, e) in self.engines.items()
        }

        return self.get_user_choice("Engine:", choice_dict)

    def get_external_db_server(self) -> str:
        return self.get_user_optional_input(
            "Server host name. Use host.docker.internal for the host machine. "
            "Leave blank if using DSN:",
        )

    def get_external_db_port(self) -> str:
        return self.get_user_optional_input(
            "Server port. Leave blank for default or if using DSN:"
        )

    def get_external_db_database_name(self) -> str:
        return self.get_user_input("Database name or DSN:")

    def get_external_db_user_name(self) -> str:
        return self.get_user_input("Username:")

    def get_external_db_user_password(self) -> str:
        return self.get_user_password("Password:")

    # -------------------------------------------------------------------------
    # Generic input
    # -------------------------------------------------------------------------

    def get_user_dir(self, text: str, default: str = "") -> str:
        completer = PathCompleter(only_directories=True, expanduser=True)
        directory = self.prompt(text, completer=completer, default=default)

        return os.path.expanduser(directory)

    def get_user_file(self, text: str) -> str:
        completer = PathCompleter(only_directories=False, expanduser=True)
        file = self.prompt(
            text,
            completer=completer,
            complete_while_typing=True,
            validator=FileValidator(),
        )

        return os.path.expanduser(file)

    def get_user_password(self, text: str) -> str:

        while True:
            first = self.prompt(
                text, is_password=True, validator=NotEmptyValidator()
            )
            second = self.prompt(
                "Enter the same password again:",
                is_password=True,
                validator=NotEmptyValidator(),
            )

            if first == second:
                break

            self.error("Passwords do not match. Try again.")

        return first

    def get_user_boolean(self, text: str) -> str:
        value = self.prompt(text, validator=YesNoValidator())
        if value.lower() == "y":
            return "1"
        return "0"

    def get_user_email(self, text: str) -> str:
        return self.prompt(text, validator=EmailValidator())

    def get_user_input(self, text: str, default: str = "") -> str:
        return self.prompt(
            text, default=default, validator=NotEmptyValidator()
        )

    def get_user_optional_input(self, text: str, default: str = "") -> str:
        return self.prompt(text, default=default)

    def get_user_choice(
        self, text: str, choice_dict: Dict, *args, **kwargs
    ) -> str:

        definitions_html = "".join(
            [
                f"<name>{name}</name> for <desc>{description}</desc>\n"
                for (name, description) in choice_dict.items()
            ]
        )

        completer = WordCompleter(choice_dict.keys())

        return self.prompt_html(
            HTML(f"<span>{text}</span>\nEnter:\n{definitions_html}\n"),
            validator=ChoiceValidator(choice_dict.keys()),
            completer=completer,
            style=self.choice_style,
        )

    def prompt(self, text: str, *args, **kwargs) -> str:
        """
        Shows a prompt and returns user input.
        """
        return self.prompt_html(
            HTML(f"\n<span>{text}</span> "),
            *args,
            **kwargs,
            style=self.prompt_style,
        )

    def prompt_html(self, html: str, *args, **kwargs) -> str:
        return prompt(
            html,
            *args,
            **kwargs,
        )

    # -------------------------------------------------------------------------
    # Generic environment variable handling
    # -------------------------------------------------------------------------

    def setenv(
        self,
        name: str,
        value_or_callable: Union[str, Callable[[], str]],
        obscure: bool = False,
    ) -> None:
        """
        Set an environment variable if it is not already set.
        Reports the final value (pre-existing or new) if we are being verbose.
        """
        if name not in os.environ:
            if isinstance(value_or_callable, str):
                value = value_or_callable
            else:
                value = value_or_callable()
            os.environ[name] = value

        value_shown = "*" * 4 if obscure else os.environ[name]
        self.envvar_info(f"{name}={value_shown}")

    @staticmethod
    def _write_envvars_to_file(
        f: TextIO, include_passwords: bool = False
    ) -> None:
        """
        We typically avoid saving passwords. Note that some of the config files
        do contain passwords.
        """
        for key, value in os.environ.items():
            if not (
                key.startswith(DockerEnvVar.PREFIX)
                or key.startswith(InstallerEnvVar.PREFIX)
            ):
                continue
            if not include_passwords and key.endswith(EnvVar.PASSWORD_SUFFIX):
                continue
            f.write(f'export {key}="{value}"\n')

    def write_environment_variables(
        self, permit_cfg_dir_save: bool = True
    ) -> None:
        config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        if config_dir and os.path.exists(config_dir) and permit_cfg_dir_save:
            filename = os.path.join(config_dir, HostPath.ENVVAR_SAVE_FILE)
            with open(filename, mode="w") as f:
                self._write_envvars_to_file(f)
        else:
            with NamedTemporaryFile(delete=False, mode="w") as f:
                filename = f.name
                self._write_envvars_to_file(f)
        self.info(
            "Settings have been saved and can be loaded with "
            f"'source {filename}'."
        )

    # -------------------------------------------------------------------------
    # Shell handling
    # -------------------------------------------------------------------------

    def run_bash_command_inside_docker(self, bash_command: str) -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        self.docker.compose.run(
            DockerComposeServices.CRATE_WORKERS,
            remove=True,
            command=[bash_command],
        )

    # -------------------------------------------------------------------------
    # Formatting
    # -------------------------------------------------------------------------

    @staticmethod
    def format_multiline(values: Iterable[str]) -> str:
        indented_values = textwrap.indent("\n".join(values), 4 * " ")
        return f"\n{indented_values}"

    # -------------------------------------------------------------------------
    # Local file handling
    # -------------------------------------------------------------------------

    def search_replace_file(
        self, filename: str, replace_dict: Dict[str, str]
    ) -> None:
        """
        Replace placeholders marked as ``@@key@@`` with the associated value,
        in the file specified.
        """
        self.info(f"Editing {filename}")
        with open(filename, "r") as f:
            contents = f.read()

        for search, replace in replace_dict.items():
            if replace is None:
                # Shouldn't happen in normal operation
                self.fail(f"Can't replace '{search}' with None")

            contents = contents.replace(f"@@{search}@@", replace)

        with open(filename, "w") as f:
            f.write(contents)


# =============================================================================
# Installer specializations
# =============================================================================


class Wsl2Installer(Installer):
    pass


class NativeLinuxInstaller(Installer):
    def report_status(self) -> None:
        server_url = self.get_crate_server_url()
        localhost_url = self.get_crate_server_localhost_url()
        self.info(
            f"The CRATE application is running at {server_url} "
            f"or {localhost_url}"
        )

    def get_crate_server_url(self) -> str:
        scheme = self.get_crate_server_scheme()
        ip_address = self.get_crate_server_ip_from_host()

        netloc = f"{ip_address}:8000"
        path = self.get_crate_server_path()
        params = query = fragment = None

        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def get_crate_server_ip_from_host(self) -> str:
        return self.get_crate_server_ip_address()


class MacOsInstaller(Installer):
    pass


# =============================================================================
# Retrieve an appropriate installer for the host OS
# =============================================================================


def get_installer_class() -> Type[Installer]:
    sys_info = uname()

    if "microsoft-standard" in sys_info.release:
        return Wsl2Installer

    if sys_info.system == "Linux":
        return NativeLinuxInstaller

    if sys_info.system == "Darwin":
        return MacOsInstaller

    if sys_info.system == "Windows":
        print(
            "The installer cannot be run under native Windows. Please "
            "install Windows Subsystem for Linux 2 (WSL2) and run the "
            "installer from there. Alternatively follow the instructions "
            "to install CRATE manually."
        )
        sys.exit(EXIT_FAILURE)

    print(f"Sorry, the installer can't be run under {sys_info.system}.")
    sys.exit(EXIT_FAILURE)


# =============================================================================
# Command-line entry point
# =============================================================================


class Command:
    EXEC_COMMAND = "exec"
    INSTALL = "install"
    RUN_COMMAND = "run"
    START = "start"
    STOP = "stop"
    SHELL = "shell"


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Be verbose")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rebuild the CRATE Docker image",
    )
    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid CRATE installer commands are:",
        help="Specify one command.",
        dest="command",
    )
    subparsers.required = True

    subparsers.add_parser(
        Command.INSTALL, help="Install CRATE into a Docker Compose environment"
    )

    subparsers.add_parser(
        Command.START, help="Start the Docker Compose application"
    )

    subparsers.add_parser(
        Command.STOP, help="Stop the Docker Compose application"
    )

    run_crate_command = subparsers.add_parser(
        Command.RUN_COMMAND,
        help=f"Run a command within the CRATE Docker environment, in the "
        f"{DockerComposeServices.CRATE_WORKERS!r} service/container",
    )
    run_crate_command.add_argument("crate_command", type=str)

    exec_crate_command = subparsers.add_parser(
        Command.EXEC_COMMAND,
        help=f"Execute a command within the CRATE Docker environment, in the "
        f"existing {DockerComposeServices.CRATE_SERVER!r} service/container",
    )
    exec_crate_command.add_argument("crate_command", type=str)

    shell = subparsers.add_parser(
        Command.SHELL,
        help=f"Start a shell (command prompt) within a already-running CRATE "
        f"Docker environment, in the "
        f"{DockerComposeServices.CRATE_SERVER!r} container",
    )
    shell.add_argument(
        "--as_root",
        action="store_true",
        help="Enter as the 'root' user instead of the 'crate' user",
        default=False,
    )

    args = parser.parse_args()

    installer = get_installer_class()(
        verbose=args.verbose,
        update=args.update,
    )

    if args.command == Command.INSTALL:
        installer.install()

    elif args.command == Command.START:
        installer.start()

    elif args.command == Command.STOP:
        installer.stop()

    elif args.command == Command.RUN_COMMAND:
        installer.run_crate_command(args.crate_command)

    elif args.command == Command.EXEC_COMMAND:
        installer.exec_crate_command(args.crate_command)

    elif args.command == Command.SHELL:
        installer.run_shell_in_crate_container(as_root=args.as_root)

    else:
        raise AssertionError("Bug")


if __name__ == "__main__":
    main()

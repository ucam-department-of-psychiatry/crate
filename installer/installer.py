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
from ``installer_boot.py``. Note that the full CRATE Python environment is NOT
available.

"""

from argparse import ArgumentParser
import collections
import grp
import html
import inspect
import io
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
    List,
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

# noinspection PyUnresolvedReferences,PyProtectedMember
from python_on_whales import docker, DockerClient, DockerException
from python_on_whales.components.container.cli_wrapper import Container

from semantic_version import Version

# Python Prompt Toolkit has basic support for text entry / yes-no / alert
# dialogs but unfortunately there is one feature lacking:
#
# Completion does not display:
# https://github.com/prompt-toolkit/python-prompt-toolkit/issues/715
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
EXIT_FAILURE = 1  # Unexpected error
EXIT_USER = 2  # User error e.g. bad command, misconfiguration, CTRL-C


class HostPath:
    """
    Directories and filenames as seen from the host OS.
    """

    DEFAULT_CRATE_ROOT_DIR = "/crate"
    ENVVAR_SAVE_FILE = "set_crate_docker_host_envvars"
    ENVVAR_UNSET_FILE = "unset_crate_docker_host_envvars"


class DockerPath:
    """
    Directories and filenames as seen from the Docker containers.
    """

    BASH = "/bin/bash"

    ROOT_DIR = "/crate"

    CONFIG_DIR = os.path.join(ROOT_DIR, "cfg")
    FILES_DIR = os.path.join(ROOT_DIR, "files")
    ARCHIVE_TEMPLATE_DIR = os.path.join(FILES_DIR, "archive_templates")
    ARCHIVE_ATTACHMENT_DIR = os.path.join(FILES_DIR, "archive_attachments")
    ARCHIVE_STATIC_DIR = os.path.join(ARCHIVE_TEMPLATE_DIR, "static")

    ARCHIVE_TEMPLATE_CACHE_DIR = os.path.join(
        FILES_DIR, "archive_template_cache"
    )
    PRIVATE_FILE_STORAGE_ROOT = os.path.join(FILES_DIR, "private")

    VENV_DIR = os.path.join(ROOT_DIR, "venv")
    CRATE_INSTALL_DIR = os.path.join(
        VENV_DIR, "lib", "python3.10", "site-packages"
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
    DOCS_HOST_DIR = f"{PREFIX}_DOCS_HOST_DIR"
    FILES_HOST_DIR = f"{PREFIX}_FILES_HOST_DIR"
    GATE_BIOYODIE_RESOURCES_HOST_DIR = (
        f"{PREFIX}_GATE_BIOYODIE_RESOURCES_HOST_DIR"
    )
    IMAGE_TAG = f"{PREFIX}_IMAGE_TAG"
    INSTALL_GROUP_ID = f"{PREFIX}_INSTALL_GROUP_ID"
    INSTALL_USER_ID = f"{PREFIX}_INSTALL_USER_ID"

    CRATE_DB_DATABASE_NAME = f"{PREFIX}_CRATE_DB_DATABASE_NAME"
    CRATE_DB_HOST_PORT = f"{PREFIX}_CRATE_DB_HOST_PORT"
    CRATE_DB_ROOT_PASSWORD = f"{PREFIX}_CRATE_DB_ROOT_{EnvVar.PASSWORD_SUFFIX}"
    CRATE_DB_USER_NAME = f"{PREFIX}_CRATE_DB_USER_NAME"
    CRATE_DB_USER_PASSWORD = f"{PREFIX}_CRATE_DB_USER_{EnvVar.PASSWORD_SUFFIX}"

    ODBC_USER_CONFIG = f"{PREFIX}_ODBC_USER_CONFIG"

    RESEARCH_DATABASE_NAME = f"{PREFIX}_RESEARCH_DATABASE_NAME"
    RESEARCH_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"
    )
    RESEARCH_DATABASE_USER_NAME = f"{PREFIX}_RESEARCH_DATABASE_USER_NAME"
    RESEARCH_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"
    )
    RESEARCH_DATABASE_HOST_PORT = f"{PREFIX}_RESEARCH_DATABASE_HOST_PORT"

    SECRET_DATABASE_NAME = f"{PREFIX}_SECRET_DATABASE_NAME"
    SECRET_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"
    )
    SECRET_DATABASE_USER_NAME = f"{PREFIX}_SECRET_DATABASE_USER_NAME"
    SECRET_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"
    )
    SECRET_DATABASE_HOST_PORT = f"{PREFIX}_SECRET_DATABASE_HOST_PORT"

    SOURCE_DATABASE_NAME = f"{PREFIX}_SOURCE_DATABASE_NAME"
    SOURCE_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_ROOT_{EnvVar.PASSWORD_SUFFIX}"
    )
    SOURCE_DATABASE_USER_NAME = f"{PREFIX}_SOURCE_DATABASE_USER_NAME"
    SOURCE_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_USER_{EnvVar.PASSWORD_SUFFIX}"
    )
    SOURCE_DATABASE_HOST_PORT = f"{PREFIX}_SOURCE_DATABASE_HOST_PORT"
    STATIC_HOST_DIR = f"{PREFIX}_STATIC_HOST_DIR"


class InstallerEnvVar(EnvVar):
    PREFIX = "CRATE_INSTALLER"

    CRATE_DB_ENGINE = f"{PREFIX}_CRATE_DB_ENGINE"
    CRATE_DB_SERVER = f"{PREFIX}_CRATE_DB_SERVER"
    CRATE_DB_PORT = f"{PREFIX}_CRATE_DB_PORT"

    CRATE_ROOT_HOST_DIR = f"{PREFIX}_CRATE_ROOT_HOST_DIR"

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
# Ports
# =============================================================================


class Ports:
    # In numeric order
    MYSQL = "3306"
    CRATEWEB = "8000"
    RABBITMQ = "5672"
    CRATE_DB_HOST = "43306"
    DEMO_RESEARCH_DB_HOST = "43307"
    DEMO_SECRET_DB_HOST = "43308"
    DEMO_SOURCE_DB_HOST = "43309"


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
# Databases
# =============================================================================


class Database(
    collections.namedtuple(
        "Database",
        [
            # Docker and external
            "short_desc",
            "long_desc",
            "engine_var",
            "host_var",
            "port_var",
            "name_var",
            "user_name_var",
            "password_var",
            # Docker MySQL only
            "root_password_var",
            "host_port_var",
        ],
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
        crate_root_dir: str = None,
        light_mode: bool = False,
        update: bool = False,
        verbose: bool = False,
    ) -> None:
        self._docker = None
        self._engines = None
        self._env_dict = None
        self._databases = None
        self.light_mode = light_mode
        self.update = update
        self.verbose = verbose

        crate_root_dir = crate_root_dir or os.getenv(
            InstallerEnvVar.CRATE_ROOT_HOST_DIR
        )
        if crate_root_dir is None:
            print(
                "You must specify --crate_root_dir or set the environment "
                "variable CRATE_INSTALLER_CRATE_ROOT_HOST_DIR"
            )

            sys.exit(EXIT_USER)

        self.title = "CRATE Setup"
        self.choice_style = self.get_choice_style()
        self.envvar_style = self.get_body_style()
        self.error_style = self.get_text_style(Colours.RED)
        self.info_style = self.get_body_style()
        self.intro_style = self.get_highlight_style()
        self.prompt_style = self.get_text_style(Colours.CYAN)
        self.success_style = self.get_text_style(Colours.GREEN)

        self.setenv(InstallerEnvVar.CRATE_ROOT_HOST_DIR, crate_root_dir)

    def get_body_style(self) -> Style:
        return self.get_text_style(self.get_body_foreground_colour())

    def get_body_foreground_colour(self) -> str:
        if self.light_mode:
            return Colours.BASE00

        return Colours.BASE0

    def get_highlight_style(self) -> Style:
        if self.light_mode:
            return self.get_text_style(
                f"bg:{Colours.BASE2} fg:{Colours.BASE01}"
            )

        return self.get_text_style(f"bg:{Colours.BASE02} fg:{Colours.BASE1}")

    @staticmethod
    def get_text_style(style_string: str) -> Style:
        return Style.from_dict({"span": style_string})

    def get_choice_style(self) -> Style:
        return Style.from_dict(
            {
                "span": Colours.CYAN,
                "name": Colours.ORANGE,
                "desc": self.get_body_foreground_colour(),
            }
        )

    @property
    def engines(self) -> Dict[str, DatabaseEngine]:
        if self._engines is None:
            self._engines = self.get_database_engines()

        return self._engines

    @staticmethod
    def get_database_engines() -> Dict[str, DatabaseEngine]:
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
    def databases(self) -> Dict[str, Database]:
        if self._databases is None:
            self._databases = self.get_databases()

        return self._databases

    def get_databases(self) -> Dict[str, Database]:
        return {
            "crate": Database(
                "CRATE database",
                "This database is used by the CRATE web application.",
                InstallerEnvVar.CRATE_DB_ENGINE,
                InstallerEnvVar.CRATE_DB_SERVER,
                InstallerEnvVar.CRATE_DB_PORT,
                DockerEnvVar.CRATE_DB_DATABASE_NAME,
                DockerEnvVar.CRATE_DB_USER_NAME,
                DockerEnvVar.CRATE_DB_USER_PASSWORD,
                DockerEnvVar.CRATE_DB_ROOT_PASSWORD,
                DockerEnvVar.CRATE_DB_HOST_PORT,
            ),
            "research": Database(
                "research database",
                (
                    "This is where the anonymised data will be stored. More "
                    "research databases can be added by manually editing the "
                    "configuration files generated by CRATE after "
                    "installation."
                ),
                InstallerEnvVar.RESEARCH_DATABASE_ENGINE,
                InstallerEnvVar.RESEARCH_DATABASE_HOST,
                InstallerEnvVar.RESEARCH_DATABASE_PORT,
                DockerEnvVar.RESEARCH_DATABASE_NAME,
                DockerEnvVar.RESEARCH_DATABASE_USER_NAME,
                DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD,
                DockerEnvVar.RESEARCH_DATABASE_ROOT_PASSWORD,
                DockerEnvVar.RESEARCH_DATABASE_HOST_PORT,
            ),
            "secret": Database(
                "secret administrative database",
                "This database stores information like Patient ID to "
                "Research ID mapping. "
                "More secret databases can be added by manually editing the "
                "configuration files generated by CRATE after installation. "
                "There should be one secret administrative database for every "
                "research database.",
                InstallerEnvVar.SECRET_DATABASE_ENGINE,
                InstallerEnvVar.SECRET_DATABASE_HOST,
                InstallerEnvVar.SECRET_DATABASE_PORT,
                DockerEnvVar.SECRET_DATABASE_NAME,
                DockerEnvVar.SECRET_DATABASE_USER_NAME,
                DockerEnvVar.SECRET_DATABASE_USER_PASSWORD,
                DockerEnvVar.SECRET_DATABASE_ROOT_PASSWORD,
                DockerEnvVar.SECRET_DATABASE_HOST_PORT,
            ),
            "source": Database(
                "source database",
                "This database contains the patient-identifiable "
                "data. More source databases can be added by manually editing "
                "the configuration files generated by CRATE after "
                "installation.",
                InstallerEnvVar.SOURCE_DATABASE_ENGINE,
                InstallerEnvVar.SOURCE_DATABASE_HOST,
                InstallerEnvVar.SOURCE_DATABASE_PORT,
                DockerEnvVar.SOURCE_DATABASE_NAME,
                DockerEnvVar.SOURCE_DATABASE_USER_NAME,
                DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD,
                DockerEnvVar.SOURCE_DATABASE_ROOT_PASSWORD,
                DockerEnvVar.SOURCE_DATABASE_HOST_PORT,
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
        self.maybe_test_database_connections()

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
        self.copy_example_scripts()

        self.report_status()

    def build_crate_image(self) -> None:
        # Only build the crate image if the tag has changed
        # or the update flag was set explicitly
        if self.image_needs_building():
            # Could set cache=False here if there are problems.
            # It looks like docker.compose.build will always rebuild the docker
            # image even if there is an existing image with the same tag.
            os.chdir(self.dockerfiles_host_dir())

            self.docker.compose.build(
                services=[
                    DockerComposeServices.CRATE_SERVER,
                    DockerComposeServices.CRATE_WORKERS,
                    DockerComposeServices.FLOWER,
                ]
            )

    def image_needs_building(self) -> bool:
        if self.update:
            return True

        os.chdir(self.dockerfiles_host_dir())

        filters = dict(reference=self.getenv(DockerEnvVar.IMAGE_TAG))
        images = self.docker.image.list(filters=filters)

        return len(images) == 0

    def maybe_test_database_connections(self) -> None:
        # Only test external database connections, not those provided by the
        # installer under Docker. Those won't exist yet.
        if not self.should_create_crate_db_container():
            self.test_database_connection(self.databases["crate"])

        if not self.should_create_demo_containers():
            self.test_database_connection(self.databases["source"])
            self.test_database_connection(self.databases["research"])
            self.test_database_connection(self.databases["secret"])

    def test_database_connection(self, db: Database) -> None:
        self.info(f"\nTesting connection to the {db.short_desc}...")
        os.chdir(self.dockerfiles_host_dir())

        error = io.StringIO()
        output = io.StringIO()

        try:
            output_generator = self.run_crate_command(
                [
                    "crate_test_database_connection",
                    self.get_db_url(db),
                ],
                stream=True,
            )
            for stream_type, stream_content in output_generator:
                decoded = stream_content.decode("utf-8")

                if stream_type == "stdout":
                    output.write(decoded)
                elif stream_type == "stderr":
                    error.write(decoded)
        except DockerException:
            self.error(output.getvalue())

            if self.verbose:
                self.error(error.getvalue(), split_lines=False)

                self.fail(
                    "Failed to connect.\n"
                    "Troubleshooting:\n"
                    "----------------\n"
                    "'Login timeout expired': Problem with server host name "
                    "or firewall?\n"
                    "'Login failed': Problem with username/password?\n"
                    "'Data source name not found...': Incorrect DSN name or "
                    "entry?\n\n"
                )

            self.fail(
                "Failed to connect. "
                "Run the installer again with --verbose to see more detail."
            )

        self.info(output.getvalue().strip())
        self.success("OK")

    def start(self) -> None:
        os.chdir(self.dockerfiles_host_dir())
        self.docker.compose.up(detach=True)

    def stop(self) -> None:
        os.chdir(self.dockerfiles_host_dir())
        self.docker.compose.down(volumes=True)

    def run_shell_in_crate_container(self, as_root: bool = False) -> None:
        os.chdir(self.dockerfiles_host_dir())

        user = "root" if as_root else None

        self.docker.compose.execute(
            DockerComposeServices.CRATE_SERVER,
            [DockerPath.BASH],
            user=user,
        )

    def run_crate_command_and_output_to_file(
        self, crate_command: List[str], filename: str
    ) -> None:
        with open(filename, "wb") as f:
            output_generator = self.run_crate_command(
                crate_command, stream=True
            )
            for stream_type, stream_content in output_generator:
                if stream_type == "stdout":
                    f.write(stream_content)
                elif stream_type == "stderr":
                    decoded = stream_content.decode("utf-8")
                    print(decoded, file=sys.stderr, end="")

    def run_crate_command(
        self,
        crate_command: List[str],
        stream: bool = False,
        tty: bool = False,
    ) -> Union[str, Container, Iterable[Tuple[str, bytes]]]:
        # Run a command in a new instance of the crate_workers container.
        # This goes through docker-entrypoint.sh so no need to source the
        # virtualenv or call /bin/bash.
        # "Run" here means "without a terminal".
        if not crate_command:
            self.error("Error: no command specified")
            sys.exit(EXIT_USER)

        if tty and stream:
            # Mirror behaviour of docker.compose.run in Python on Whales
            raise ValueError(
                "You can't set tty=True and stream=True at the same"
                "time. Their purpose are not compatible."
            )

        os.chdir(self.dockerfiles_host_dir())

        return self.docker.compose.run(
            DockerComposeServices.CRATE_WORKERS,
            remove=True,
            stream=stream,
            tty=tty,
            command=crate_command,
        )

    def exec_crate_command(
        self, crate_command: str, as_root: bool = False
    ) -> None:
        # Execute a command in the existing instance of the crate_server
        # container. This does not go through entrypoint.sh, so we have to
        # source the virtualenv and call /bin/bash
        # "Execute" here means "with a terminal".
        venv_command = f'""source /crate/venv/bin/activate; {crate_command}""'

        user = "root" if as_root else None

        os.chdir(self.dockerfiles_host_dir())

        self.docker.compose.execute(
            DockerComposeServices.CRATE_SERVER,
            [DockerPath.BASH, "-c", venv_command],
            user=user,
        )

    # -------------------------------------------------------------------------
    # Info messages
    # -------------------------------------------------------------------------

    def report(
        self, text: str, style: Style, split_lines: bool = True
    ) -> None:
        span = self.span(text, split_lines=split_lines)
        print_formatted_text(HTML(span), style=style)

    def start_message(self) -> None:
        self.report("CRATE Installer", self.intro_style)
        if self.light_mode:
            return self.report(
                "Running in light mode. "
                "Remove the --light_mode option to run in dark mode.",
                self.get_highlight_style(),
            )

        self.report(
            "Running in dark mode. "
            "Use the --light_mode option to run in light mode.",
            self.get_highlight_style(),
        )

    def highlight(self, text: str) -> None:
        self.report(text, self.get_highlight_style())

    def info(self, text: str) -> None:
        self.report(text, self.info_style)

    def success(self, text: str) -> None:
        self.report(text, self.success_style)

    def envvar_info(self, text: str) -> None:
        if not self.verbose:
            return
        self.report(text, self.envvar_style)

    def error(self, text: str, split_lines: bool = True) -> None:
        self.report(text, self.error_style, split_lines=split_lines)

    def fail(self, text: str) -> NoReturn:
        self.error(text)
        sys.exit(EXIT_USER)

    def dump_colours(self) -> None:
        # Development only
        colour_attrs = inspect.getmembers(
            Colours, lambda attr: not inspect.isroutine(attr)
        )

        for name, value in colour_attrs:
            if name.startswith("__"):
                continue

            style = Style.from_dict(
                {
                    "span": value,
                }
            )

            self.report(name, style)

        self.report(
            "Dark body",
            Style.from_dict(
                {"span": f"bg:{Colours.BASE03} fg:{Colours.BASE0}"}
            ),
        )
        self.report(
            "Dark highlights",
            Style.from_dict(
                {"span": f"bg:{Colours.BASE02} fg:{Colours.BASE1}"}
            ),
        )

        self.report(
            "Light body",
            Style.from_dict(
                {"span": f"bg:{Colours.BASE3} fg:{Colours.BASE00}"}
            ),
        )
        self.report(
            "Light highlights",
            Style.from_dict(
                {"span": f"bg:{Colours.BASE2} fg:{Colours.BASE01}"}
            ),
        )

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
            raw_version = docker.compose.version().split()[-1]
            # Sometimes this has a leading 'v'; sometimes it looks like
            # '2.20.2+ds1-0ubuntu1~22.04.1', so also split on "+" or "~":
            version_string = re.split(r"[+~]", raw_version.lstrip("v"))[0]
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
            self.configure_group()
            self.configure_config_files()
            self.configure_docs_dir()
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
            self.configure_tag()
        except (KeyboardInterrupt, EOFError):
            # The user pressed CTRL-C or CTRL-D
            self.abort_installation()

    def abort_installation(self) -> None:
        self.error("Installation aborted")
        self.write_environment_variables()
        sys.exit(EXIT_USER)

    def configure_user(self) -> None:
        self.setenv(
            DockerEnvVar.INSTALL_USER_ID, self.get_docker_install_user_id
        )

    def configure_group(self) -> None:
        self.setenv(
            DockerEnvVar.INSTALL_GROUP_ID, self.get_docker_install_group_id
        )

    def configure_tag(self) -> None:
        tag = self.env_dict[DockerEnvVar.IMAGE_TAG]
        self.setenv(DockerEnvVar.IMAGE_TAG, tag)

    @property
    def env_dict(self) -> Dict[str, str]:
        # Variables set in .env
        if self._env_dict is None:
            self._env_dict = self.read_env_file()

        return self._env_dict

    def read_env_file(self) -> Dict[str, str]:
        env_file = os.path.join(self.dockerfiles_host_dir(), ".env")

        env_dict = {}

        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line == "" or line.startswith("#"):
                    continue

                parts = line.split("=")
                env_dict[parts[0]] = parts[1]

        return env_dict

    def configure_config_files(self) -> None:
        self.setenv(
            DockerEnvVar.CONFIG_HOST_DIR, self.default_config_host_dir()
        )
        self.setenv(
            DockerEnvVar.GATE_BIOYODIE_RESOURCES_HOST_DIR,
            self.default_gate_bioyodie_resources_host_dir(),
        )
        self.setenv(
            DockerEnvVar.CRATEWEB_CONFIG_FILENAME, "crateweb_local_settings.py"
        )
        self.setenv(DockerEnvVar.CRATE_ANON_CONFIG, "crate_anon_config.ini")
        self.setenv(DockerEnvVar.ODBC_USER_CONFIG, "odbc_user.ini")

    def configure_files_dir(self) -> None:
        self.setenv(DockerEnvVar.FILES_HOST_DIR, self.default_files_host_dir())

    def configure_docs_dir(self) -> None:
        self.setenv(DockerEnvVar.DOCS_HOST_DIR, self.default_docs_host_dir())

    def configure_static_dir(self) -> None:
        self.setenv(
            DockerEnvVar.STATIC_HOST_DIR, self.default_static_host_dir()
        )

    def configure_crateweb(self) -> None:
        self.setenv(
            DockerEnvVar.CRATEWEB_HOST_PORT, self.get_docker_crateweb_host_port
        )
        self.setenv(
            InstallerEnvVar.CRATEWEB_USE_HTTPS,
            self.get_crateweb_use_https,
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
            self.configure_crate_db_container()

        self.configure_external_db(self.databases["crate"])

    def configure_crate_db_container(self) -> None:
        return self.configure_docker_db(
            self.databases["crate"],
            host="crate_db",
            root_password=self.get_docker_crate_db_root_password,
            database_name="crate_web_db",
            user_name="crate_web_user",
            user_password=self.get_docker_crate_db_user_password,
            host_port=self.get_docker_crate_db_host_port,
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

        self.configure_external_db(self.databases["source"])
        self.configure_external_db(self.databases["research"])
        self.configure_external_db(self.databases["secret"])

    def configure_demo_research_db(self) -> None:
        self.configure_docker_db(
            self.databases["research"],
            host="research_db",
            root_password="research",
            database_name="research",
            user_name="research",
            user_password="research",
            host_port=Ports.DEMO_RESEARCH_DB_HOST,
        )

    def configure_demo_secret_db(self) -> None:
        self.configure_docker_db(
            self.databases["secret"],
            host="secret_db",
            root_password="secret",
            database_name="secret",
            user_name="secret",
            user_password="secret",
            host_port=Ports.DEMO_SECRET_DB_HOST,
        )

    def configure_demo_source_db(self) -> None:
        self.configure_docker_db(
            self.databases["source"],
            host="source_db",
            root_password="source",
            database_name="source",
            user_name="source",
            user_password="source",
            host_port=Ports.DEMO_SOURCE_DB_HOST,
        )

    def configure_docker_db(
        self,
        db: Database,
        host: Union[str, Callable[[], str]],
        root_password: Union[str, Callable[[], str]],
        database_name: Union[str, Callable[[], str]],
        user_name: Union[str, Callable[[], str]],
        user_password: Union[str, Callable[[], str]],
        host_port: Union[str, Callable[[], str]],
    ):
        self.setenv(db.engine_var, "mysql")
        self.setenv(db.host_var, host)
        self.setenv(db.port_var, Ports.MYSQL)
        self.setenv(db.root_password_var, root_password, obscure=True)
        self.setenv(db.name_var, database_name)
        self.setenv(db.user_name_var, user_name)
        self.setenv(db.password_var, user_password, obscure=True)
        self.setenv(db.host_port_var, host_port)

    def configure_external_db(self, db: Database) -> None:
        if self.external_db_configured(db):
            return

        self.report(
            f"\nEnter the details of the {db.short_desc}. {db.long_desc}",
            self.prompt_style,
        )
        self.external_db_instructions()

        self.setenv(db.engine_var, self.get_external_db_engine)
        self.setenv(db.host_var, self.get_external_db_server)
        self.setenv(db.port_var, self.get_external_db_port)
        self.setenv(db.name_var, self.get_external_db_database_name)
        self.setenv(db.user_name_var, self.get_external_db_user_name)
        self.setenv(
            db.password_var,
            self.get_external_db_user_password,
            obscure=True,
        )

    def external_db_configured(self, db: Database) -> bool:
        for var in [
            db.engine_var,
            db.host_var,
            db.port_var,
            db.name_var,
            db.user_name_var,
            db.password_var,
        ]:
            if os.getenv(var) is None:
                return False

        return True

    def external_db_instructions(self) -> None:
        self.info(
            "CRATE will attempt to connect to the external database during "
            "installation."
        )
        self.highlight("Before continuing:")
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
        cherrypy_args = ["--host 0.0.0.0", f"--port {Ports.CRATEWEB}"]

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
            f"{DockerComposeServices.RABBITMQ}:{Ports.RABBITMQ}",
        ]

        if self.should_create_crate_db_container():
            wait_for.append(f"{DockerComposeServices.CRATE_DB}:{Ports.MYSQL}")
        #
        if self.should_create_demo_containers():
            wait_for.extend(
                [
                    f"{DockerComposeServices.RESEARCH_DB}:{Ports.MYSQL}",
                    f"{DockerComposeServices.SECRET_DB}:{Ports.MYSQL}",
                    f"{DockerComposeServices.SOURCE_DB}:{Ports.MYSQL}",
                ]
            )

        self.setenv(DockerEnvVar.CRATE_WAIT_FOR, " ".join(wait_for))

    @staticmethod
    def create_directories() -> None:
        crate_config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        Path(crate_config_dir).mkdir(parents=True, exist_ok=True)

        crate_docs_dir = os.environ.get(DockerEnvVar.DOCS_HOST_DIR)
        Path(crate_docs_dir).mkdir(parents=True, exist_ok=True)

        crate_files_dir = os.environ.get(DockerEnvVar.FILES_HOST_DIR)
        Path(crate_files_dir).mkdir(parents=True, exist_ok=True)

        crate_logs_dir = os.path.join(crate_files_dir, "logs")
        Path(crate_logs_dir).mkdir(parents=True, exist_ok=True)

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
# Server = host.docker.internal
# User = username
# Password = password
# Database = name_of_database
# For multiple result sets:
# MARS_Connection = yes

# [put_name_of_second_dsn_here]
# ...
"""

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
                ["crate_print_demo_crateweb_config", "--leave_placeholders"],
                settings,
            )
        self.configure_local_settings()

    def configure_local_settings(self) -> None:
        crate_database_name = self.getenv(DockerEnvVar.CRATE_DB_DATABASE_NAME)
        research_database_name = self.getenv(
            DockerEnvVar.RESEARCH_DATABASE_NAME
        )
        secret_database_name = self.getenv(DockerEnvVar.SECRET_DATABASE_NAME)

        crate_database_options = "{}"
        research_database_options = "{}"
        secret_database_options = "{}"

        if self.use_dsn_for_crate_db():
            crate_database_options = f'{{"dsn": "{crate_database_name}"}}'

        if self.use_dsn_for_research_db():
            research_database_options = (
                f'{{"dsn": "{research_database_name}"}}'
            )

        if self.use_dsn_for_secret_db():
            secret_database_options = f'{{"dsn": "{secret_database_name}"}}'

        research_engine_name = self.getenv(
            InstallerEnvVar.RESEARCH_DATABASE_ENGINE
        )

        rdikeys_database = ""
        rdikeys_schema = ""

        if research_engine_name == "mssql":
            rdikeys_database = research_database_name
            rdikeys_schema = "dbo"

        if research_engine_name == "mysql":
            rdikeys_schema = research_database_name

        if research_engine_name == "postgresql":
            # untested
            rdikeys_schema = "public"

        replace_dict = {
            "archive_attachment_dir": DockerPath.ARCHIVE_ATTACHMENT_DIR,
            "archive_static_dir": DockerPath.ARCHIVE_STATIC_DIR,
            "archive_template_cache_dir": DockerPath.ARCHIVE_TEMPLATE_CACHE_DIR,  # noqa: E501
            "archive_template_dir": DockerPath.ARCHIVE_TEMPLATE_DIR,
            "broker_url": f"amqp://rabbitmq:{Ports.RABBITMQ}",
            "crate_db_engine": self.engines[
                self.getenv(InstallerEnvVar.CRATE_DB_ENGINE)
            ].django,
            "crate_db_name": crate_database_name,
            "crate_db_host": self.getenv(InstallerEnvVar.CRATE_DB_SERVER),
            "crate_db_options": crate_database_options,
            "crate_db_password": self.getenv(
                DockerEnvVar.CRATE_DB_USER_PASSWORD
            ),
            "crate_db_port": self.getenv(InstallerEnvVar.CRATE_DB_PORT),
            "crate_db_user": self.getenv(DockerEnvVar.CRATE_DB_USER_NAME),
            "crate_https": str(self.use_https()),
            "crate_install_dir": DockerPath.CRATE_INSTALL_DIR,
            "dest_db_engine": self.engines[research_engine_name].django,
            "dest_db_host": self.getenv(
                InstallerEnvVar.RESEARCH_DATABASE_HOST
            ),
            "dest_db_options": research_database_options,
            "dest_db_port": self.getenv(
                InstallerEnvVar.RESEARCH_DATABASE_PORT
            ),
            "dest_db_name": research_database_name,
            "dest_db_user": self.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_NAME
            ),
            "dest_db_password": self.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD
            ),
            "django_site_root_absolute_url": "http://mymachine.mydomain",
            "force_script_name": self.get_crate_server_path(),
            "pdf_logo_abs_url": "file:///crate/cfg/crate_logo.png",
            "private_file_storage_root": DockerPath.PRIVATE_FILE_STORAGE_ROOT,
            "rdi1_name": "research",
            "rdi1_description": "Research database",
            "rdi1_database": rdikeys_database,
            "rdi1_schema": rdikeys_schema,
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
                self.getenv(InstallerEnvVar.SECRET_DATABASE_ENGINE)
            ].django,
            "secret_db1_host": self.getenv(
                InstallerEnvVar.SECRET_DATABASE_HOST
            ),
            "secret_db1_port": self.getenv(
                InstallerEnvVar.SECRET_DATABASE_PORT
            ),
            "secret_db1_name": self.getenv(DockerEnvVar.SECRET_DATABASE_NAME),
            "secret_db1_options": secret_database_options,
            "secret_db1_user": self.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_NAME
            ),
            "secret_db1_password": self.getenv(
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
                ["crate_anon_demo_config", "--leave_placeholders"], config
            )
        self.configure_anon_config()

    def configure_anon_config(self) -> None:
        replace_dict = {
            "data_dictionary_filename": self.get_data_dictionary_docker_filename(),  # noqa: E501
            "per_table_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "master_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "change_detection_encryption_phrase": self.get_hmac_md5_key(),
            "dest_db_url": self.get_db_url(self.databases["research"]),
            "admin_db_url": self.get_db_url(self.databases["secret"]),
            "source_db1_url": self.get_db_url(self.databases["source"]),
            "source_db1_ddgen_include_fields": "Note.note",
            "source_db1_ddgen_scrubsrc_patient_fields": self.format_multiline(
                ("forename", "surname")
            ),
        }

        self.search_replace_file(self.anon_config_full_path(), replace_dict)

    def copy_ssl_files(self) -> None:
        config_dir = self.getenv(DockerEnvVar.CONFIG_HOST_DIR)

        cert_dest = os.path.join(config_dir, "crate.crt")
        key_dest = os.path.join(config_dir, "crate.key")

        shutil.copy(
            self.getenv(InstallerEnvVar.CRATEWEB_SSL_CERTIFICATE), cert_dest
        )
        shutil.copy(
            self.getenv(InstallerEnvVar.CRATEWEB_SSL_PRIVATE_KEY), key_dest
        )

    def create_or_update_crate_database(self) -> None:
        self.run_crate_command(["crate_django_manage", "migrate"], tty=True)

    def collect_static(self) -> None:
        self.run_crate_command(
            ["crate_django_manage", "collectstatic", "--no-input"], tty=True
        )

    def populate(self) -> None:
        self.run_crate_command(["crate_django_manage", "populate"], tty=True)

    def create_superuser(self) -> None:
        # Will either create a superuser or update an existing one
        # with the given username
        self.run_crate_command(
            ["crate_django_manage", "ensuresuperuser"], tty=True
        )

    def create_demo_data(self) -> None:
        url = self.get_db_url(self.databases["source"])
        self.run_crate_command(["crate_make_demo_database", url], tty=True)

    def create_data_dictionary(self) -> None:
        self.info("Creating data dictionary...")
        data_dictionary = self.get_data_dictionary_host_filename()
        self.run_crate_command_and_output_to_file(
            ["crate_anon_draft_dd"], data_dictionary
        )

    def anonymise_demo_data(self) -> None:
        self.info("Anonymising demo data...")
        self.run_crate_command(["crate_anonymise", "--full"], tty=True)

    def copy_example_scripts(self) -> None:
        scripts_dir = self.crate_scripts_host_dir()

        if os.path.exists(scripts_dir):
            self.info(
                "Scripts directory already exists. Not copying examples."
            )
            return

        self.info("Copying example scripts...")
        shutil.copytree(
            self.installer_examples_scripts_host_dir(), scripts_dir
        )

        set_crate_environment_vars = os.path.join(
            scripts_dir, "set_crate_environment_vars"
        )
        replace_dict = {
            "CRATE_HOST_BASE_DIR": self.crate_root_host_dir(),
            "CRATE_HOST_CONFIG_DIR": self.getenv(DockerEnvVar.CONFIG_HOST_DIR),
        }
        self.search_replace_file(set_crate_environment_vars, replace_dict)

    def report_status(self) -> None:
        localhost_url = self.get_crate_server_localhost_url()
        self.success(f"The CRATE application is running at {localhost_url}")

    # -------------------------------------------------------------------------
    # Fetching information from environment variables or statically
    # -------------------------------------------------------------------------

    def get_docker_install_user_id(self) -> str:
        return str(self._get_user_id())

    def get_docker_install_group_id(self) -> str:
        self.info(
            "\nThe CRATE Docker image will be created with your user ID and "
            "one of your user's group IDs so that file permissions will be "
            "correct for any file systems shared between the host and "
            "container."
        )
        # This is a bit slow with sssd
        self.info("Fetching groups...")
        choice_dict = {}

        # https://stackoverflow.com/questions/9323834/python-how-to-get-group-ids-of-one-username-like-id-gn
        # Works with sssd. Maybe not everything else.
        for group_id in os.getgroups():
            # Ignore any groups created by the OS so we don't clash when we try
            # to create a group with the same ID on the server
            if group_id >= 1000:
                try:
                    choice_dict[str(group_id)] = grp.getgrgid(group_id).gr_name
                except KeyError:
                    # One poster reported that this happens for some reason
                    pass

        if len(choice_dict) == 1:
            group_id = next(iter(choice_dict))
            name = choice_dict[group_id]
            self.info(
                f"Only one group '{name}' found for this user. Using that."
            )
            return group_id

        return self.get_user_choice(
            choice_dict,
            intro_text=(
                "Select the group to use. If a mounted file system needs to "
                "be shared between multiple users, choose a group that "
                "includes all of those users."
            ),
        )

    @staticmethod
    def _get_user_id() -> int:
        return os.geteuid()

    @staticmethod
    def get_hmac_md5_key() -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16))

    def local_settings_full_path(self) -> str:
        return os.path.join(
            self.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            self.getenv(DockerEnvVar.CRATEWEB_CONFIG_FILENAME),
        )

    def anon_config_full_path(self) -> str:
        return os.path.join(
            self.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            self.getenv(DockerEnvVar.CRATE_ANON_CONFIG),
        )

    def odbc_config_full_path(self) -> str:
        return os.path.join(
            self.getenv(DockerEnvVar.CONFIG_HOST_DIR),
            self.getenv(DockerEnvVar.ODBC_USER_CONFIG),
        )

    def get_data_dictionary_host_filename(self) -> str:
        return os.path.join(
            self.getenv(DockerEnvVar.CONFIG_HOST_DIR), "data_dictionary.tsv"
        )

    @staticmethod
    def get_data_dictionary_docker_filename() -> str:
        return os.path.join(DockerPath.CONFIG_DIR, "data_dictionary.tsv")

    def get_db_url(self, db: Database) -> str:
        return self.get_sqlalchemy_url(
            self.getenv(db.engine_var),
            self.getenv(db.user_name_var),
            self.getenv(db.password_var),
            self.getenv(db.host_var),
            self.getenv(db.port_var),
            self.getenv(db.name_var),
        )

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
        url_encoded_password = urllib.parse.quote_plus(password)
        netloc = f"{user}:{url_encoded_password}@"
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

    def use_https(self) -> bool:
        return self.getenv(InstallerEnvVar.CRATEWEB_USE_HTTPS) == "1"

    def should_create_crate_db_container(self) -> bool:
        create = self.getenv(InstallerEnvVar.CREATE_CRATE_DB_CONTAINER)
        if create is None:
            self.fail(
                f"{InstallerEnvVar.CREATE_CRATE_DB_CONTAINER} "
                "should be set to 0 or 1"
            )

        return create == "1"

    def should_create_demo_containers(self) -> bool:
        create = self.getenv(InstallerEnvVar.CREATE_DEMO_DB_CONTAINERS)
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

    def get_crate_server_port_from_host(self) -> str:
        return self.getenv(DockerEnvVar.CRATEWEB_HOST_PORT)

    def use_dsn_for_crate_db(self) -> bool:
        return (
            self.getenv(InstallerEnvVar.CRATE_DB_ENGINE) == "mssql"
            and self.getenv(InstallerEnvVar.CRATE_DB_SERVER) == ""
        )

    def use_dsn_for_research_db(self) -> bool:
        return (
            self.getenv(InstallerEnvVar.RESEARCH_DATABASE_ENGINE) == "mssql"
            and self.getenv(InstallerEnvVar.RESEARCH_DATABASE_HOST) == ""
        )

    def use_dsn_for_secret_db(self) -> bool:
        return (
            self.getenv(InstallerEnvVar.SECRET_DATABASE_ENGINE) == "mssql"
            and self.getenv(InstallerEnvVar.SECRET_DATABASE_HOST) == ""
        )

    def dockerfiles_host_dir(self) -> str:
        return os.path.join(self.docker_host_dir(), "dockerfiles")

    def docker_host_dir(self) -> str:
        return os.path.join(self.src_host_dir(), "docker")

    def src_host_dir(self) -> str:
        return os.path.join(self.installer_host_dir(), os.pardir)

    def installer_examples_scripts_host_dir(self) -> str:
        return os.path.join(self.installer_host_dir(), "example_scripts")

    def installer_host_dir(self) -> str:
        return os.path.dirname(os.path.realpath(__file__))

    def default_config_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "config")

    def default_static_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "static")

    def default_docs_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "docs")

    def default_files_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "files")

    def default_gate_bioyodie_resources_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "bioyodie_resources")

    def crate_root_host_dir(self) -> str:
        return self.getenv(InstallerEnvVar.CRATE_ROOT_HOST_DIR)

    def crate_scripts_host_dir(self) -> str:
        return os.path.join(self.crate_root_host_dir(), "scripts")

    # -------------------------------------------------------------------------
    # Fetching information from the user
    # -------------------------------------------------------------------------

    def get_docker_crateweb_host_port(self) -> str:
        return self.get_user_input(
            (
                "Enter the port where the CRATE web app will appear on the "
                "host:"
            ),
            default=Ports.CRATEWEB,
        )

    def get_crateweb_use_https(self) -> str:
        return self.get_user_boolean(
            "Access the CRATE web app directly over HTTPS? "
            "Answer 'n' if HTTPS traffic will be routed via a web server "
            "(e.g. Apache) (y/n)"
        )

    def get_crateweb_ssl_certificate(self) -> str:
        return self.get_user_file("Select the SSL certificate file:")

    def get_crateweb_ssl_private_key(self) -> str:
        return self.get_user_file("Select the SSL private key file:")

    def get_create_crate_db_container(self) -> str:
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
            default=Ports.CRATE_DB_HOST,
        )

    def get_create_demo_containers(self) -> str:
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

        return self.get_user_choice(choice_dict, prompt_text="Engine:")

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
        self,
        choice_dict: Dict,
        intro_text: str = None,
        prompt_text: str = "Enter:",
    ) -> str:
        definitions_html = "".join(
            [
                f"<name>{name}</name> for <desc>{description}</desc>\n"
                for (name, description) in choice_dict.items()
            ]
        )

        # noinspection PyTypeChecker
        completer = WordCompleter(choice_dict.keys())

        lines = []
        if intro_text is not None:
            lines.append(f"{intro_text}")

        lines.append(prompt_text)
        span = self.span("\n\n".join(lines))

        return self.prompt_html(
            HTML(f"\n{span}\n{definitions_html}\n"),
            validator=ChoiceValidator(choice_dict.keys()),
            completer=completer,
            style=self.choice_style,
        )

    def prompt(self, text: str, *args, **kwargs) -> str:
        """
        Shows a prompt and returns user input.
        """
        span = self.span(f"\n{text}")
        return self.prompt_html(
            HTML(f"{span} "),
            *args,
            **kwargs,
            style=self.prompt_style,
        )

    def span(
        self, text: str, split_lines: bool = True, escape: bool = True
    ) -> str:
        """
        Returns span HTML fragment, with options to escape and split lines.
        """
        if split_lines:
            lines = text.split("\n")
            text = "\n".join([textwrap.fill(line, width=80) for line in lines])

        if escape:
            text = html.escape(text)

        return f"<span>{text}</span>"

    @staticmethod
    def prompt_html(html: Union[str, HTML], *args, **kwargs) -> str:
        return prompt(
            html,
            *args,
            **kwargs,
        )

    # -------------------------------------------------------------------------
    # Generic environment variable handling
    # -------------------------------------------------------------------------
    def getenv(self, name: str, fail_if_unset: bool = True) -> str:
        value = os.getenv(name)
        if value is None and fail_if_unset:
            self.fail(
                f"The environment variable {name} is not set. This may be "
                "because you haven't yet run the installer with the 'install' "
                "command or you haven't set this environment variable "
                "following a previous install:\n"
                f"(source /path/to/{HostPath.ENVVAR_SAVE_FILE})."
            )

        return value

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
        for key, value in sorted(os.environ.items()):
            if not (
                key.startswith(DockerEnvVar.PREFIX)
                or key.startswith(InstallerEnvVar.PREFIX)
            ):
                continue
            if not include_passwords and key.endswith(EnvVar.PASSWORD_SUFFIX):
                continue
            f.write(f'export {key}="{value}"\n')

    @staticmethod
    def _write_envvar_unsets_to_file(f: TextIO) -> None:
        for key, value in sorted(os.environ.items()):
            if key.startswith(DockerEnvVar.PREFIX) or key.startswith(
                InstallerEnvVar.PREFIX
            ):
                f.write(f"unset {key}\n")

    def write_environment_variables(
        self, permit_cfg_dir_save: bool = True
    ) -> None:
        config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        if config_dir and os.path.exists(config_dir) and permit_cfg_dir_save:
            envvar_save_file = os.path.join(
                config_dir, HostPath.ENVVAR_SAVE_FILE
            )
            with open(envvar_save_file, mode="w") as f:
                self._write_envvars_to_file(f)
            envvar_unset_file = os.path.join(
                config_dir, HostPath.ENVVAR_UNSET_FILE
            )
            with open(envvar_unset_file, mode="w") as f:
                self._write_envvar_unsets_to_file(f)

        else:
            with NamedTemporaryFile(delete=False, mode="w") as f:
                envvar_save_file = f.name
                self._write_envvars_to_file(f)
            with NamedTemporaryFile(delete=False, mode="w") as f:
                envvar_unset_file = f.name
                self._write_envvar_unsets_to_file(f)
        self.highlight("Settings have been saved and can be loaded with:")
        self.info(f"source {envvar_save_file}")
        self.highlight("To unset all settings:")
        self.info(f"source {envvar_unset_file}")

    # -------------------------------------------------------------------------
    # Shell handling
    # -------------------------------------------------------------------------

    def run_bash_command_inside_docker(self, bash_command: str) -> None:
        os.chdir(self.dockerfiles_host_dir())
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
        self.success(
            f"The CRATE application is running at {server_url} "
            f"or {localhost_url}"
        )

    def get_crate_server_url(self) -> str:
        scheme = self.get_crate_server_scheme()
        ip_address = self.get_crate_server_ip_from_host()

        netloc = f"{ip_address}:{Ports.CRATEWEB}"
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
            "to install CRATE manually.",
            file=sys.stderr,
        )
        sys.exit(EXIT_USER)

    print(
        f"Sorry, the installer can't be run under {sys_info.system}.",
        file=sys.stderr,
    )

    sys.exit(EXIT_USER)


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
        "--crate_root_dir",
        help=(
            "Top level CRATE directory containing config files and source "
            "code (if not running the installer locally)"
        ),
    )
    parser.add_argument(
        "--light_mode",
        action="store_true",
        default=False,
        help="Use this if your terminal has a light background",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rebuild the CRATE Docker image.",
    )
    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid CRATE installer commands are:",
        help="Specify one command.",
        dest="command",
    )
    subparsers.required = True

    subparsers.add_parser(
        Command.INSTALL,
        help="Install CRATE into a Docker Compose environment.",
    )
    subparsers.add_parser(
        Command.START, help="Start the Docker Compose application."
    )

    subparsers.add_parser(
        Command.STOP, help="Stop the Docker Compose application."
    )

    run_crate_command = subparsers.add_parser(
        Command.RUN_COMMAND,
        help=f"Run a command within the CRATE Docker environment, in the "
        f"{DockerComposeServices.CRATE_WORKERS!r} service/container (without "
        f"a terminal, so output will not be visible).",
    )
    run_crate_command.add_argument("crate_command", type=str)

    exec_crate_command = subparsers.add_parser(
        Command.EXEC_COMMAND,
        help=f"Execute a command within the CRATE Docker environment, in the "
        f"existing {DockerComposeServices.CRATE_SERVER!r} service/container "
        f"(with a terminal, so output is visible).",
    )
    exec_crate_command.add_argument("crate_command", type=str)
    exec_crate_command.add_argument(
        "--as_root",
        action="store_true",
        help="Enter as the 'root' user instead of the 'crate' user",
        default=False,
    )

    shell = subparsers.add_parser(
        Command.SHELL,
        help=f"Start a shell (command prompt) within a already-running CRATE "
        f"Docker environment, in the "
        f"{DockerComposeServices.CRATE_SERVER!r} container.",
    )
    shell.add_argument(
        "--as_root",
        action="store_true",
        help="Enter as the 'root' user instead of the 'crate' user",
        default=False,
    )

    args = parser.parse_args()

    installer = get_installer_class()(
        crate_root_dir=args.crate_root_dir,
        light_mode=args.light_mode,
        update=args.update,
        verbose=args.verbose,
    )

    if args.command == Command.INSTALL:
        installer.install()

    elif args.command == Command.START:
        installer.start()

    elif args.command == Command.STOP:
        installer.stop()

    elif args.command == Command.RUN_COMMAND:
        installer.run_crate_command(args.crate_command, tty=True)

    elif args.command == Command.EXEC_COMMAND:
        installer.exec_crate_command(args.crate_command, as_root=args.as_root)

    elif args.command == Command.SHELL:
        installer.run_shell_in_crate_container(as_root=args.as_root)

    else:
        raise AssertionError("Bug")


if __name__ == "__main__":
    main()

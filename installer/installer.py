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
import os
from pathlib import Path
from platform import uname
import re
import secrets
import shutil
import string
from subprocess import run
import sys
from tempfile import NamedTemporaryFile
import textwrap
from typing import Callable, Dict, Iterable, NoReturn, TextIO, Type, Union
import urllib.parse

# See installer-requirements.txt
from prompt_toolkit import HTML, print_formatted_text, prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator, ValidationError

# noinspection PyUnresolvedReferences
from python_on_whales import docker, DockerException
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
    Subset of services named in ``docker/dockerfiles/docker-compose.yaml``.
    """

    CRATE_SERVER = "crate_server"
    CRATE_WORKERS = "crate_workers"
    FLOWER = "flower"


class DockerEnvVar:
    """
    Environment variables governing the Docker setup.
    """

    PREFIX = "CRATE_DOCKER"
    PASSWORD_SUFFIX = "PASSWORD"

    CONFIG_HOST_DIR = f"{PREFIX}_CONFIG_HOST_DIR"
    CRATE_ANON_CONFIG = f"{PREFIX}_CRATE_ANON_CONFIG"
    CRATEWEB_CONFIG_FILENAME = f"{PREFIX}_CRATEWEB_CONFIG_FILENAME"
    CRATEWEB_HOST_PORT = f"{PREFIX}_CRATEWEB_HOST_PORT"
    CRATEWEB_SSL_CERTIFICATE = f"{PREFIX}_CRATEWEB_SSL_CERTIFICATE"
    CRATEWEB_SSL_PRIVATE_KEY = f"{PREFIX}_CRATEWEB_SSL_PRIVATE_KEY"
    CRATEWEB_SUPERUSER_EMAIL = f"{PREFIX}_CRATEWEB_SUPERUSER_EMAIL"
    CRATEWEB_SUPERUSER_PASSWORD = (
        f"{PREFIX}_CRATEWEB_SUPERUSER_{PASSWORD_SUFFIX}"  # noqa
    )
    CRATEWEB_SUPERUSER_USERNAME = f"{PREFIX}_CRATEWEB_SUPERUSER_USERNAME"
    CRATEWEB_USE_HTTPS = f"{PREFIX}_CRATEWEB_USE_HTTPS"
    GATE_BIOYODIE_RESOURCES_HOST_DIR = (
        f"{PREFIX}_GATE_BIOYODIE_RESOURCES_HOST_DIR"  # noqa
    )
    INSTALL_USER_ID = f"{PREFIX}_INSTALL_USER_ID"

    MYSQL_CRATE_DATABASE_NAME = f"{PREFIX}_MYSQL_CRATE_DATABASE_NAME"
    MYSQL_CRATE_HOST_PORT = f"{PREFIX}_MYSQL_CRATE_HOST_PORT"
    MYSQL_CRATE_ROOT_PASSWORD = f"{PREFIX}_MYSQL_CRATE_ROOT_{PASSWORD_SUFFIX}"
    MYSQL_CRATE_USER_NAME = f"{PREFIX}_MYSQL_CRATE_USER_NAME"
    MYSQL_CRATE_USER_PASSWORD = f"{PREFIX}_MYSQL_CRATE_USER_{PASSWORD_SUFFIX}"

    ODBC_USER_CONFIG = f"{PREFIX}_ODBC_USER_CONFIG"

    RESEARCH_DATABASE_ENGINE = f"{PREFIX}_RESEARCH_DATABASE_ENGINE"
    RESEARCH_DATABASE_HOST = f"{PREFIX}_RESEARCH_DATABASE_HOST"
    RESEARCH_DATABASE_NAME = f"{PREFIX}_RESEARCH_DATABASE_NAME"
    RESEARCH_DATABASE_PORT = f"{PREFIX}_RESEARCH_DATABASE_PORT"
    RESEARCH_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_ROOT_{PASSWORD_SUFFIX}"  # noqa
    )
    RESEARCH_DATABASE_USER_NAME = f"{PREFIX}_RESEARCH_DATABASE_USER_NAME"
    RESEARCH_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_RESEARCH_DATABASE_USER_{PASSWORD_SUFFIX}"  # noqa
    )

    SECRET_DATABASE_ENGINE = f"{PREFIX}_SECRET_DATABASE_ENGINE"
    SECRET_DATABASE_HOST = f"{PREFIX}_SECRET_DATABASE_HOST"
    SECRET_DATABASE_NAME = f"{PREFIX}_SECRET_DATABASE_NAME"
    SECRET_DATABASE_PORT = f"{PREFIX}_SECRET_DATABASE_PORT"
    SECRET_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_ROOT_{PASSWORD_SUFFIX}"  # noqa
    )
    SECRET_DATABASE_USER_NAME = f"{PREFIX}_SECRET_DATABASE_USER_NAME"
    SECRET_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SECRET_DATABASE_USER_{PASSWORD_SUFFIX}"  # noqa
    )

    SOURCE_DATABASE_ENGINE = f"{PREFIX}_SOURCE_DATABASE_ENGINE"
    SOURCE_DATABASE_HOST = f"{PREFIX}_SOURCE_DATABASE_HOST"
    SOURCE_DATABASE_NAME = f"{PREFIX}_SOURCE_DATABASE_NAME"
    SOURCE_DATABASE_PORT = f"{PREFIX}_SOURCE_DATABASE_PORT"
    SOURCE_DATABASE_ROOT_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_ROOT_{PASSWORD_SUFFIX}"  # noqa
    )
    SOURCE_DATABASE_USER_NAME = f"{PREFIX}_SOURCE_DATABASE_USER_NAME"
    SOURCE_DATABASE_USER_PASSWORD = (
        f"{PREFIX}_SOURCE_DATABASE_USER_{PASSWORD_SUFFIX}"  # noqa
    )
    STATIC_HOST_DIR = f"{PREFIX}_STATIC_HOST_DIR"


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


class PasswordMatchValidator(Validator):
    def __init__(self, first_password: str) -> None:
        self.first_password = first_password

    def validate(self, document: Document) -> None:
        password = document.text

        if password != self.first_password:
            raise ValidationError(message="Passwords do not match")


class EmailValidator(Validator):
    _SIMPLE_EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def validate(self, document: Document) -> None:
        email = document.text
        if self._SIMPLE_EMAIL_REGEX.match(email) is None:
            raise ValidationError(message=f"{email!r} is not a valid e-mail")


# =============================================================================
# Installer base class
# =============================================================================


class Installer:
    def __init__(
        self,
        verbose: bool = False,
        update: bool = False,
    ) -> None:
        self.verbose = verbose
        self.update = update

        self.title = "CRATE Setup"
        self.intro_style = Style.from_dict(
            {
                "span": "#ffffff bg:#0000b8",
            }
        )
        self.prompt_style = Style.from_dict(
            {
                "span": "#ffffff bg:#005eb8",
            }
        )
        self.info_style = Style.from_dict(
            {
                "span": "#00cc00 bg:#000000",
            }
        )
        self.error_style = Style.from_dict(
            {
                "span": "#ffffff bg:#b80000",
            }
        )
        self.envvar_style = Style.from_dict(
            {
                "span": "#008800 bg:#000000",
            }
        )

    # -------------------------------------------------------------------------
    # Commands
    # -------------------------------------------------------------------------

    def install(self) -> None:
        self.start_message()
        self.check_setup()
        self.configure()
        self.write_environment_variables()

        if self.update:
            self.rebuild_crate_image()

        self.create_directories()
        self.write_odbc_config()
        self.create_local_settings()
        self.create_anon_config()
        if self.use_https():
            self.copy_ssl_files()
        self.create_or_update_crate_database()
        self.collect_static()
        self.populate()
        self.create_superuser()
        self.start()
        self.create_demo_data()
        self.create_data_dictionary()
        self.anonymise_demo_data()
        self.report_status()

    def rebuild_crate_image(self) -> None:
        self.info("Updating existing CRATE installation")
        os.chdir(HostPath.DOCKERFILES_DIR)
        docker.compose.build(
            services=[
                DockerComposeServices.CRATE_SERVER,
                DockerComposeServices.CRATE_WORKERS,
                DockerComposeServices.FLOWER,
            ],
            cache=False,
        )

    @staticmethod
    def start() -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        docker.compose.up(detach=True)

    @staticmethod
    def stop() -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        docker.compose.down()

    @staticmethod
    def run_shell_in_crate_container(as_root: bool = False) -> None:
        # python_on_whales doesn't support docker compose exec yet
        os.chdir(HostPath.DOCKERFILES_DIR)

        command = ["docker", "compose", "exec"]
        user_option = ["-u", "0"] if as_root else []

        run(
            command
            + user_option
            + [DockerComposeServices.CRATE_SERVER, DockerPath.BASH]
        )

    def run_crate_command(self, crate_command: str) -> None:
        self.run_bash_command_inside_docker(
            f"source /crate/venv/bin/activate; {crate_command}"
        )

    def exec_crate_command(self, crate_command: str) -> None:
        venv_command = f'""source /crate/venv/bin/activate; {crate_command}""'

        os.chdir(HostPath.DOCKERFILES_DIR)

        docker.compose.execute(
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
            self.configure_static_dir()
            self.configure_crateweb()
            self.configure_crate_db()
            self.configure_research_db()
            self.configure_secret_db()
            self.configure_source_db()
            self.configure_django()
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

    def configure_static_dir(self) -> None:
        self.setenv(
            DockerEnvVar.STATIC_HOST_DIR, self.get_docker_static_host_dir
        )

    def configure_crateweb(self) -> None:
        self.setenv(
            DockerEnvVar.CRATEWEB_HOST_PORT, self.get_docker_crateweb_host_port
        )
        self.setenv(
            DockerEnvVar.CRATEWEB_USE_HTTPS, self.get_docker_crateweb_use_https
        )
        if self.use_https():
            self.setenv(
                DockerEnvVar.CRATEWEB_SSL_CERTIFICATE,
                self.get_docker_crateweb_ssl_certificate,
            )
            self.setenv(
                DockerEnvVar.CRATEWEB_SSL_PRIVATE_KEY,
                self.get_docker_crateweb_ssl_private_key,
            )

    def configure_crate_db(self) -> None:
        self.setenv(
            DockerEnvVar.MYSQL_CRATE_ROOT_PASSWORD,
            self.get_docker_mysql_crate_root_password,
            obscure=True,
        )
        self.setenv(DockerEnvVar.MYSQL_CRATE_DATABASE_NAME, "crate_web_db")
        self.setenv(DockerEnvVar.MYSQL_CRATE_USER_NAME, "crate_web_user")
        self.setenv(
            DockerEnvVar.MYSQL_CRATE_USER_PASSWORD,
            self.get_docker_mysql_crate_user_password,
            obscure=True,
        )
        self.setenv(
            DockerEnvVar.MYSQL_CRATE_HOST_PORT,
            self.get_docker_mysql_crate_host_port,
        )

    def configure_research_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(DockerEnvVar.RESEARCH_DATABASE_ENGINE, "mysql")
        self.setenv(DockerEnvVar.RESEARCH_DATABASE_HOST, "research_db")
        self.setenv(DockerEnvVar.RESEARCH_DATABASE_PORT, "3306")
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

    def configure_secret_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(DockerEnvVar.SECRET_DATABASE_ENGINE, "mysql")
        self.setenv(DockerEnvVar.SECRET_DATABASE_HOST, "secret_db")
        self.setenv(DockerEnvVar.SECRET_DATABASE_PORT, "3306")
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_ROOT_PASSWORD, "secret", obscure=True
        )
        self.setenv(DockerEnvVar.SECRET_DATABASE_NAME, "secret")
        self.setenv(DockerEnvVar.SECRET_DATABASE_USER_NAME, "secret")
        self.setenv(
            DockerEnvVar.SECRET_DATABASE_USER_PASSWORD, "secret", obscure=True
        )

    def configure_source_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(DockerEnvVar.SOURCE_DATABASE_ENGINE, "mysql")
        self.setenv(DockerEnvVar.SOURCE_DATABASE_HOST, "source_db")
        self.setenv(DockerEnvVar.SOURCE_DATABASE_PORT, "3306")
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_ROOT_PASSWORD, "source", obscure=True
        )
        self.setenv(DockerEnvVar.SOURCE_DATABASE_NAME, "source")
        self.setenv(DockerEnvVar.SOURCE_DATABASE_USER_NAME, "source")
        self.setenv(
            DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD, "source", obscure=True
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

    @staticmethod
    def create_directories() -> None:
        crate_config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        Path(crate_config_dir).mkdir(parents=True, exist_ok=True)

        crate_static_dir = os.environ.get(DockerEnvVar.STATIC_HOST_DIR)
        Path(crate_static_dir).mkdir(parents=True, exist_ok=True)

        bioyodie_resources_dir = os.environ.get(
            DockerEnvVar.GATE_BIOYODIE_RESOURCES_HOST_DIR
        )
        Path(bioyodie_resources_dir).mkdir(parents=True, exist_ok=True)

    def write_odbc_config(self) -> None:
        demo_config = r"""# Example ODBC DSN definition

# [put_name_of_dsn_here]
# Driver = /opt/microsoft/msodbcsql17/lib64/libmsodbcsql-17.10.so.2.1
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
            self.info(f"Writing ODBC config: {config}")
            with open(config, "w") as f:
                f.write(demo_config)

    def create_local_settings(self) -> None:
        settings = self.local_settings_full_path()
        if not os.path.exists(settings):
            self.info(f"Creating {settings}")
            Path(settings).touch()
            self.run_crate_command(
                "crate_print_demo_crateweb_config --leave_placeholders > "
                "$CRATE_WEB_LOCAL_SETTINGS"
            )
        self.configure_local_settings()

    def configure_local_settings(self) -> None:
        replace_dict = {
            "archive_attachment_dir": DockerPath.ARCHIVE_ATTACHMENT_DIR,
            "archive_static_dir": DockerPath.ARCHIVE_STATIC_DIR,
            "archive_template_cache_dir": DockerPath.ARCHIVE_TEMPLATE_CACHE_DIR,  # noqa: E501
            "archive_template_dir": DockerPath.ARCHIVE_TEMPLATE_DIR,
            "broker_url": "amqp://rabbitmq:5672",
            "crate_https": str(self.use_https()),
            "crate_install_dir": DockerPath.CRATE_INSTALL_DIR,
            "dest_db_engine": self.get_django_engine(
                os.getenv(DockerEnvVar.RESEARCH_DATABASE_ENGINE)
            ),
            "dest_db_host": os.getenv(DockerEnvVar.RESEARCH_DATABASE_HOST),
            "dest_db_port": os.getenv(DockerEnvVar.RESEARCH_DATABASE_PORT),
            "dest_db_name": os.getenv(DockerEnvVar.RESEARCH_DATABASE_NAME),
            "dest_db_user": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_NAME
            ),
            "dest_db_password": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD
            ),
            "django_site_root_absolute_url": "http://mymachine.mydomain",
            "force_script_name": self.get_crate_server_path(),
            "mysql_db": os.getenv(DockerEnvVar.MYSQL_CRATE_DATABASE_NAME),
            "mysql_host": "crate_db",
            "mysql_password": os.getenv(
                DockerEnvVar.MYSQL_CRATE_USER_PASSWORD
            ),
            "mysql_port": "3306",
            "mysql_user": os.getenv(DockerEnvVar.MYSQL_CRATE_USER_NAME),
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
            "secret_db1_engine": self.get_django_engine(
                os.getenv(DockerEnvVar.SECRET_DATABASE_ENGINE)
            ),
            "secret_db1_host": os.getenv(DockerEnvVar.SECRET_DATABASE_HOST),
            "secret_db1_port": os.getenv(DockerEnvVar.SECRET_DATABASE_PORT),
            "secret_db1_name": os.getenv(DockerEnvVar.SECRET_DATABASE_NAME),
            "secret_db1_user": os.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_NAME
            ),
            "secret_db1_password": os.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_PASSWORD
            ),
        }

        self.search_replace_file(self.local_settings_full_path(), replace_dict)

    def create_anon_config(self) -> None:
        config = self.anon_config_full_path()
        if not os.path.exists(config):
            self.info(f"Creating {config}")
            Path(config).touch()
            self.run_crate_command(
                "crate_anon_demo_config --leave_placeholders > "
                "$CRATE_ANON_CONFIG"
            )
        self.configure_anon_config()

    def configure_anon_config(self) -> None:
        replace_dict = {
            "data_dictionary_filename": self.get_data_dictionary_filename(),
            "per_table_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "master_patient_id_encryption_phrase": self.get_hmac_md5_key(),
            "change_detection_encryption_phrase": self.get_hmac_md5_key(),
            "dest_db_engine": self.get_sqlalchemy_engine(
                os.getenv(DockerEnvVar.RESEARCH_DATABASE_ENGINE)
            ),
            "dest_db_user": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_NAME
            ),
            "dest_db_password": os.getenv(
                DockerEnvVar.RESEARCH_DATABASE_USER_PASSWORD,
            ),
            "dest_db_host": os.getenv(DockerEnvVar.RESEARCH_DATABASE_HOST),
            "dest_db_port": os.getenv(DockerEnvVar.RESEARCH_DATABASE_PORT),
            "dest_db_name": os.getenv(DockerEnvVar.RESEARCH_DATABASE_NAME),
            "admin_db_engine": self.get_sqlalchemy_engine(
                os.getenv(DockerEnvVar.SECRET_DATABASE_ENGINE)
            ),
            "admin_db_user": os.getenv(DockerEnvVar.SECRET_DATABASE_USER_NAME),
            "admin_db_password": os.getenv(
                DockerEnvVar.SECRET_DATABASE_USER_PASSWORD
            ),
            "admin_db_host": os.getenv(DockerEnvVar.SECRET_DATABASE_HOST),
            "admin_db_port": os.getenv(DockerEnvVar.SECRET_DATABASE_PORT),
            "admin_db_name": os.getenv(DockerEnvVar.SECRET_DATABASE_NAME),
            "source_db1_engine": self.get_sqlalchemy_engine(
                os.getenv(DockerEnvVar.SOURCE_DATABASE_ENGINE)
            ),
            "source_db1_user": os.getenv(
                DockerEnvVar.SOURCE_DATABASE_USER_NAME
            ),
            "source_db1_password": os.getenv(
                DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD
            ),
            "source_db1_host": os.getenv(DockerEnvVar.SOURCE_DATABASE_HOST),
            "source_db1_port": os.getenv(DockerEnvVar.SOURCE_DATABASE_PORT),
            "source_db1_name": os.getenv(DockerEnvVar.SOURCE_DATABASE_NAME),
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
            os.getenv(DockerEnvVar.CRATEWEB_SSL_CERTIFICATE), cert_dest
        )
        shutil.copy(os.getenv(DockerEnvVar.CRATEWEB_SSL_PRIVATE_KEY), key_dest)

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
        dialect = os.getenv(DockerEnvVar.SOURCE_DATABASE_ENGINE)
        user = os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_NAME)
        password = os.getenv(DockerEnvVar.SOURCE_DATABASE_USER_PASSWORD)
        host = os.getenv(DockerEnvVar.SOURCE_DATABASE_HOST)
        port = os.getenv(DockerEnvVar.SOURCE_DATABASE_PORT)
        name = os.getenv(DockerEnvVar.SOURCE_DATABASE_NAME)
        url = self.get_sqlalchemy_url(
            dialect, user, password, host, port, name
        )
        self.run_crate_command(f"crate_make_demo_database {url}")

    def create_data_dictionary(self) -> None:
        data_dictionary = self.get_data_dictionary_filename()
        self.run_crate_command(f"crate_anon_draft_dd > {data_dictionary}")

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
    def get_data_dictionary_filename() -> str:
        return "/crate/cfg/data_dictionary.tsv"

    def get_sqlalchemy_url(
        self,
        dialect: str,
        user: str,
        password: str,
        host: str,
        port: str,
        name: str,
    ) -> str:
        scheme = self.get_sqlalchemy_engine(dialect)
        netloc = f"{user}:{password}@{host}:{port}"
        path = name
        query = "charset=utf8"
        params = fragment = None
        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    @staticmethod
    def get_sqlalchemy_engine(label: str) -> str:
        engines = {
            "mysql": "mysql+mysqldb",
            "oracle": "oracle+cxoracle",
            "postgresql": "postgresql+psycopg2",
        }
        return engines[label]

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
        return os.getenv(DockerEnvVar.CRATEWEB_USE_HTTPS) == "1"

    @staticmethod
    def get_crate_server_path() -> str:
        return "/crate"

    @staticmethod
    def get_crate_server_ip_address() -> str:
        container = docker.container.inspect("crate_crate_server")
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
            "Access the CRATE web app over HTTPS (y/n)?"
        )

    def get_docker_crateweb_ssl_certificate(self) -> str:
        return self.get_user_file("Select the SSL certificate file:")

    def get_docker_crateweb_ssl_private_key(self) -> str:
        return self.get_user_file("Select the SSL private key file:")

    def get_docker_mysql_crate_root_password(self) -> str:
        return self.get_user_password(
            "Enter a new MySQL root password for CRATE's internal database:"
        )

    def get_docker_mysql_crate_user_password(self) -> str:
        username = os.environ[DockerEnvVar.MYSQL_CRATE_USER_NAME]
        return self.get_user_password(
            f"Enter a new password for the internal MySQL user ({username!r}) "
            f"that CRATE will create:"
        )

    def get_docker_mysql_crate_host_port(self) -> str:
        return self.get_user_input(
            (
                "Enter the port where CRATE's internal MySQL database will "
                "appear on the host:"
            ),
            default="43306",
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

    @staticmethod
    def get_django_engine(label: str) -> str:
        engines = {
            "mysql": "django.db.backends.mysql",
            "oracle": "django.db.backends.oracle",
            "postgresql": "django.db.backends.postgresql",
        }

        return engines[label]

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
        first = self.prompt(
            text, is_password=True, validator=NotEmptyValidator()
        )
        self.prompt(
            "Enter the same password again:",
            is_password=True,
            validator=PasswordMatchValidator(first),
        )
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

    def prompt(self, text: str, *args, **kwargs) -> str:
        """
        Shows a prompt and returns user input.
        """
        return prompt(
            HTML(f"\n<span>{text}</span> "),
            *args,
            **kwargs,
            style=self.prompt_style,
        )

    # -------------------------------------------------------------------------
    # Generic environment variable handling
    # -------------------------------------------------------------------------

    def setenv(
        self,
        name: str,
        value: Union[str, Callable[[], str]],
        obscure: bool = False,
    ) -> None:
        """
        Set an environment variable if it is not already set.
        Reports the final value (pre-existing or new) if we are being verbose.
        """
        if name not in os.environ:
            if not isinstance(value, str):
                value = value()
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
            if not key.startswith(DockerEnvVar.PREFIX):
                continue
            if not include_passwords and key.endswith(
                DockerEnvVar.PASSWORD_SUFFIX
            ):
                continue
            f.write(f"export {key}={value}\n")

    def write_environment_variables(
        self, permit_cfg_dir_save: bool = True
    ) -> None:
        config_dir = os.environ.get(DockerEnvVar.CONFIG_HOST_DIR)
        if config_dir and permit_cfg_dir_save:
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

    @staticmethod
    def run_bash_command_inside_docker(bash_command: str) -> None:
        os.chdir(HostPath.DOCKERFILES_DIR)
        docker.compose.run(
            DockerComposeServices.CRATE_WORKERS,
            remove=True,
            command=[DockerPath.BASH, "-c", bash_command],
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
        port = self.get_crate_server_port_from_host()

        netloc = f"{ip_address}:{port}"
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

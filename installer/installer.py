#!/usr/bin/env python

import json
import os
from pathlib import Path
from platform import uname
import sys
import secrets
import shutil
from subprocess import PIPE, run
import textwrap
from typing import Callable, Dict, Iterable, Optional, Union
import urllib

from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import input_dialog, message_dialog, yes_no_dialog
from python_on_whales import docker

EXIT_FAILURE = 1

INSTALLER_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.join(INSTALLER_DIR, "..")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")
DOCKERFILES_DIR = os.path.join(DOCKER_DIR, "dockerfiles")


class Installer:
    def __init__(self) -> None:
        self.title = "CRATE Setup"

    def install(self) -> None:
        self.check_setup()
        self.configure()
        self.create_directories()
        self.create_local_settings()
        self.create_anon_config()
        if self.use_https():
            self.copy_ssl_files()
        self.create_crate_database()
        self.collect_static()
        self.populate()
        self.create_superuser()
        self.start()
        self.create_demo_data()
        self.create_data_dictionary()
        self.anonymise_demo_data()
        self.report_status()

    def check_setup(self) -> None:
        info = docker.info()
        if info.id is None:
            print("Could not connect to Docker. Check that Docker is running "
                  "and your user is in the 'docker' group.")
            sys.exit(EXIT_FAILURE)

    def configure(self) -> None:
        self.configure_user()
        self.configure_config_files()
        self.configure_crateweb()
        self.configure_crate_db()
        self.configure_research_db()
        self.configure_secret_db()
        self.configure_source_db()
        self.configure_django()

    def configure_user(self) -> None:
        self.setenv(
            "CRATE_DOCKER_INSTALL_USER_ID",
            self.get_docker_install_user_id
        )
        self.setenv(
            "CRATE_DOCKER_INSTALL_GROUP_ID",
            self.get_docker_install_group_id
        )

    def configure_config_files(self) -> None:
        self.setenv(
            "CRATE_DOCKER_CONFIG_HOST_DIR",
            self.get_docker_config_host_dir
        )
        self.setenv(
            "CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR",
            self.get_docker_gate_bioyodie_resources_host_dir
        )
        self.setenv(
            "CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME",
            "crateweb_local_settings.py"
        )
        self.setenv(
            "CRATE_DOCKER_CRATE_ANON_CONFIG",
            "crate_anon_config.ini"
        )

    def configure_crateweb(self) -> None:
        self.setenv(
            "CRATE_DOCKER_CRATEWEB_HOST_PORT",
            self.get_docker_crateweb_host_port
        )
        self.setenv(
            "CRATE_DOCKER_CRATEWEB_USE_HTTPS",
            self.get_docker_crateweb_use_https
        )
        if self.use_https():
            self.setenv(
                "CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE",
                self.get_docker_crateweb_ssl_certificate
            )
            self.setenv(
                "CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY",
                self.get_docker_crateweb_ssl_private_key
            )

    def configure_crate_db(self) -> None:
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_ROOT_PASSWORD",
            self.get_docker_mysql_crate_root_password
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME",
            "crate_web_db"
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_USER_NAME",
            "crate_web_user"
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD",
            self.get_docker_mysql_crate_user_password
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_HOST_PORT",
            self.get_docker_mysql_crate_host_port
        )

    def configure_research_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_ENGINE",
            "mysql"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_HOST",
            "research_db"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_PORT",
            "3306"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_ROOT_PASSWORD",
            "research"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_NAME",
            "research"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_USER_NAME",
            "research"
        )
        self.setenv(
            "CRATE_DOCKER_RESEARCH_DATABASE_USER_PASSWORD",
            "research"
        )

    def configure_secret_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_ENGINE",
            "mysql"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_HOST",
            "secret_db"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_PORT",
            "3306"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_ROOT_PASSWORD",
            "secret"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_NAME",
            "secret"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_USER_NAME",
            "secret"
        )
        self.setenv(
            "CRATE_DOCKER_SECRET_DATABASE_USER_PASSWORD",
            "secret"
        )

    def configure_source_db(self) -> None:
        # TODO: Prompt user for these?
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_ENGINE",
            "mysql"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_HOST",
            "source_db"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_PORT",
            "3306"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_ROOT_PASSWORD",
            "source"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_NAME",
            "source"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_USER_NAME",
            "source"
        )
        self.setenv(
            "CRATE_DOCKER_SOURCE_DATABASE_USER_PASSWORD",
            "source"
        )

    def configure_django(self) -> None:
        self.setenv(
            "CRATE_DOCKER_DJANGO_SUPERUSER_USERNAME",
            self.get_docker_django_superuser_username
        )
        self.setenv(
            "CRATE_DOCKER_DJANGO_SUPERUSER_PASSWORD",
            self.get_docker_django_superuser_password
        )
        self.setenv(
            "CRATE_DOCKER_DJANGO_SUPERUSER_EMAIL",
            self.get_docker_django_superuser_email
        )

    def get_docker_install_user_id(self) -> str:
        return str(os.geteuid())

    def get_docker_install_group_id(self) -> str:
        return str(os.getegid())

    def get_docker_config_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the directory where CRATE will store its configuration"
        )

    def get_docker_gate_bioyodie_resources_host_dir(self) -> str:
        return self.get_user_dir(
            "Select the directory where CRATE will store Bio-YODIE resources"
        )

    def get_docker_crateweb_host_port(self) -> str:
        return self.get_user_input(
            ("Enter the port where the CRATE web app will be appear on the "
             "host")
        )

    def get_docker_crateweb_use_https(self) -> str:
        return self.get_user_boolean("Access the CRATE web app over HTTPS?")

    def get_docker_crateweb_ssl_certificate(self) -> str:
        return self.get_user_file(
            "Select the SSL certificate file."
        )

    def get_docker_crateweb_ssl_private_key(self) -> str:
        return self.get_user_file(
            "Select the SSL private key file."
        )

    def get_docker_mysql_crate_root_password(self) -> str:
        return self.get_user_password(
            "Enter a new MySQL root password for CRATE's internal database"
        )

    def get_docker_mysql_crate_user_password(self) -> str:
        return self.get_user_password(
            "Enter a new password for the MySQL user that CRATE will create"
        )

    def get_docker_mysql_crate_host_port(self) -> str:
        return self.get_user_input(
            ("Enter the port where CRATE's internal MySQL database will appear "
             "on the host."),
            default="43306"  # TODO: Default not yet working
        )

    def get_docker_django_superuser_username(self) -> str:
        return self.get_user_input(
            "Enter the user name for the CRATE administrator"
        )

    def get_docker_django_superuser_password(self) -> str:
        return self.get_user_password(
            "Enter the password for the CRATE administrator"
        )

    def get_docker_django_superuser_email(self) -> str:
        return self.get_user_input(
            "Enter the email address for the CRATE administrator"
        )

    def setenv(self, name: str, value: Union[str, Callable[[], str]]) -> None:
        if name not in os.environ:
            if not isinstance(value, str):
                value = value()

            os.environ[name] = value

    def get_user_dir(self, text: str, title: Optional[str] = None) -> str:
        if title is None:
            title = self.title

        text = f"{text}\nPress Ctrl-N to autocomplete"
        completer = PathCompleter(only_directories=True, expanduser=True)
        dir = input_dialog(title=title, text=text,
                           completer=completer).run()
        if dir is None:
            sys.exit(EXIT_FAILURE)

        return dir

    def get_user_file(self, text: str, title: Optional[str] = None) -> str:
        if title is None:
            title = self.title

        text = f"{text}\nPress Ctrl-N to autocomplete"
        completer = PathCompleter(only_directories=False, expanduser=True)
        file = input_dialog(title=title, text=text,
                            completer=completer).run()
        if file is None:
            sys.exit(EXIT_FAILURE)

        return file

    def get_user_password(self, text: str,
                          title: Optional[str] = None) -> str:
        if title is None:
            title = self.title

        while(True):
            first = input_dialog(title=title, text=text, password=True).run()
            if first is None:
                sys.exit(EXIT_FAILURE)

            second = input_dialog(title=title,
                                  text="Enter the same password again",
                                  password=True).run()
            if second is None:
                sys.exit(EXIT_FAILURE)

            if first == second:
                return first

            self.alert("Passwords did not match. Please try again.")

    def alert(self, text: str) -> None:
        message_dialog(title=self.title, text=text).run()

    def get_user_boolean(self, text: str, title: Optional[str] = None) -> str:
        if title is None:
            title = self.title

        value = yes_no_dialog(title=title, text=text).run()
        if value is None:
            sys.exit(EXIT_FAILURE)

        if value:
            return "1"

        return "0"

    def get_user_input(self, text: str, title: Optional[str] = None,
                       default: str = "") -> str:
        if title is None:
            title = self.title

        # TODO: No way of passing default to input_dialog()
        # https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1544
        #
        # Either we create a PR to do so or write our own input_dialog()
        app = input_dialog(title=title, text=text)
        value = app.run()
        if value is None:
            sys.exit(EXIT_FAILURE)

        return value

    def create_directories(self) -> None:
        crate_config_dir = os.environ.get("CRATE_DOCKER_CONFIG_HOST_DIR")
        Path(crate_config_dir).mkdir(parents=True, exist_ok=True)

        bioyodie_resources_dir = os.environ.get(
            "CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR")
        Path(bioyodie_resources_dir).mkdir(parents=True, exist_ok=True)

    def create_local_settings(self) -> None:
        if not os.path.exists(self.local_settings_full_path()):
            self.run_crate_command("crate_print_demo_crateweb_config > "
                                   "$CRATE_WEB_LOCAL_SETTINGS")

        self.configure_local_settings()

    def configure_local_settings(self) -> None:
        root_dir = "/crate"
        config_dir = os.path.join(root_dir, "cfg")
        archive_template_dir = os.path.join(config_dir, "archive_templates")
        tmp_dir = os.path.join(root_dir, "tmp")
        venv_dir = os.path.join(root_dir, "venv")
        crate_install_dir = os.path.join(venv_dir, "lib", "python3.7",
                                         "site-packages")

        replace_dict = {
            "archive_attachment_dir": os.path.join(config_dir,
                                                   "archive_attachments"),
            "archive_static_dir": os.path.join(archive_template_dir, "static"),
            "archive_template_cache_dir": os.path.join(
                archive_template_dir, "cache"
            ),
            "archive_template_dir": archive_template_dir,
            "broker_url": "amqp://rabbitmq:5672",
            "crate_install_dir": crate_install_dir,
            "dest_db_engine": self.get_django_engine(
                os.getenv("CRATE_DOCKER_RESEARCH_DATABASE_ENGINE")
            ),
            "dest_db_host": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_HOST"
            ),
            "dest_db_port": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_PORT"
            ),
            "dest_db_name": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_NAME"
            ),
            "dest_db_user": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_USER_NAME"
            ),
            "dest_db_password": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_USER_PASSWORD"
            ),
            "django_site_root_absolute_url": "http://crate_server:8088",
            "force_script_name": self.get_crate_server_path(),
            "crate_https": str(self.use_https()),
            "mysql_db": os.getenv("CRATE_DOCKER_MYSQL_CRATE_DATABASE_NAME"),
            "mysql_host": "crate_db",
            "mysql_password": os.getenv(
                "CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD"
            ),
            "mysql_port": "3306",
            "mysql_user": os.getenv("CRATE_DOCKER_MYSQL_CRATE_USER_NAME"),
            "pdf_logo_abs_url": "http://localhost/crate_logo",  # TODO
            "private_file_storage_root": os.path.join(tmp_dir, "files"),
            "secret_key": secrets.token_urlsafe(),
            "secret_db1_engine": self.get_django_engine(
                os.getenv("CRATE_DOCKER_SECRET_DATABASE_ENGINE")
            ),
            "secret_db1_host": os.getenv("CRATE_DOCKER_SECRET_DATABASE_HOST"),
            "secret_db1_port": os.getenv("CRATE_DOCKER_SECRET_DATABASE_PORT"),
            "secret_db1_name": os.getenv("CRATE_DOCKER_SECRET_DATABASE_NAME"),
            "secret_db1_user": os.getenv(
                "CRATE_DOCKER_SECRET_DATABASE_USER_NAME"
            ),
            "secret_db1_password": os.getenv(
                "CRATE_DOCKER_SECRET_DATABASE_USER_PASSWORD"
            ),
        }

        self.search_replace_file(self.local_settings_full_path(), replace_dict)

    def get_django_engine(self, label: str) -> str:
        engines = {
            "mysql": "django.db.backends.mysql",
            "oracle": "django.db.backends.oracle",
            "postgresql": "django.db.backends.postgresql",
        }

        return engines[label]

    def create_anon_config(self) -> None:
        if not os.path.exists(self.anon_config_full_path()):
            self.run_crate_command("crate_anonymise --democonfig > "
                                   "$CRATE_ANON_CONFIG")
        self.configure_anon_config()

    def configure_anon_config(self) -> None:
        replace_dict = {
            "data_dictionary_filename": self.get_data_dictionary_filename(),
            "dest_db_engine": self.get_sqlalchemy_engine(
                os.getenv("CRATE_DOCKER_RESEARCH_DATABASE_ENGINE")
            ),
            "dest_db_user": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_USER_NAME"
            ),
            "dest_db_password": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_USER_PASSWORD"
            ),
            "dest_db_host": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_HOST"
            ),
            "dest_db_port": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_PORT"
            ),
            "dest_db_name": os.getenv(
                "CRATE_DOCKER_RESEARCH_DATABASE_NAME"
            ),
            "admin_db_engine": self.get_sqlalchemy_engine(
                os.getenv("CRATE_DOCKER_SECRET_DATABASE_ENGINE")
            ),
            "admin_db_user": os.getenv(
                "CRATE_DOCKER_SECRET_DATABASE_USER_NAME"
            ),
            "admin_db_password": os.getenv(
                "CRATE_DOCKER_SECRET_DATABASE_USER_PASSWORD"
            ),
            "admin_db_host": os.getenv("CRATE_DOCKER_SECRET_DATABASE_HOST"),
            "admin_db_port": os.getenv("CRATE_DOCKER_SECRET_DATABASE_PORT"),
            "admin_db_name": os.getenv("CRATE_DOCKER_SECRET_DATABASE_NAME"),
            "source_db1_engine": self.get_sqlalchemy_engine(
                os.getenv("CRATE_DOCKER_SOURCE_DATABASE_ENGINE")
            ),
            "source_db1_user": os.getenv(
                "CRATE_DOCKER_SOURCE_DATABASE_USER_NAME"
            ),
            "source_db1_password": os.getenv(
                "CRATE_DOCKER_SOURCE_DATABASE_USER_PASSWORD"
            ),
            "source_db1_host": os.getenv(
                "CRATE_DOCKER_SOURCE_DATABASE_HOST"
            ),
            "source_db1_port": os.getenv(
                "CRATE_DOCKER_SOURCE_DATABASE_PORT"
            ),
            "source_db1_name": os.getenv(
                "CRATE_DOCKER_SOURCE_DATABASE_NAME"
            ),
            "source_db1_ddgen_include_fields": "Note.note",
            "source_db1_ddgen_scrubsrc_patient_fields": self.format_multiline(
                ("forename", "surname")
            )
        }

        self.search_replace_file(self.anon_config_full_path(), replace_dict)

    def format_multiline(self, values: Iterable[str]) -> str:
        indented_values = textwrap.indent("\n".join(values), 4*" ")
        return f"\n{indented_values}"

    def search_replace_file(self, filename: str,
                            replace_dict: Dict[str, str]) -> None:
        with open(filename, "r") as f:
            contents = f.read()

        for (search, replace) in replace_dict.items():
            if replace is None:
                print(f"Can't replace '{search}' with None")
                sys.exit(EXIT_FAILURE)

            contents = contents.replace(f"@@{search}@@", replace)

        with open(filename, "w") as f:
            f.write(contents)

    def local_settings_full_path(self) -> str:
        return os.path.join(
            os.getenv("CRATE_DOCKER_CONFIG_HOST_DIR"),
            os.getenv("CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME")
        )

    def anon_config_full_path(self) -> str:
        return os.path.join(
            os.getenv("CRATE_DOCKER_CONFIG_HOST_DIR"),
            os.getenv("CRATE_DOCKER_CRATE_ANON_CONFIG")
        )

    def copy_ssl_files(self) -> str:
        config_dir = os.getenv("CRATE_DOCKER_CONFIG_HOST_DIR")

        cert_dest = os.path.join(config_dir, "crate.crt")
        key_dest = os.path.join(config_dir, "crate.key")

        shutil.copy(os.getenv("CRATE_DOCKER_CRATEWEB_SSL_CERTIFICATE"),
                    cert_dest)
        shutil.copy(os.getenv("CRATE_DOCKER_CRATEWEB_SSL_PRIVATE_KEY"),
                    key_dest)

    def create_crate_database(self) -> None:
        self.run_crate_command("crate_django_manage migrate")

    def collect_static(self) -> None:
        self.run_crate_command("crate_django_manage collectstatic --no-input")

    def populate(self) -> None:
        self.run_crate_command("crate_django_manage populate")

    def create_superuser(self) -> None:
        # Will either create a superuser or update an existing one
        # with the given username
        self.run_crate_command("crate_django_manage ensuresuperuser")

    def run_crate_command(self, crate_command: str) -> None:
        self.run_bash_command(
            f"source /crate/venv/bin/activate; {crate_command}"
        )

    def run_bash_command(self, bash_command: str) -> None:
        os.chdir(DOCKERFILES_DIR)

        docker.compose.run("crate_workers",
                           remove=True,
                           command=["/bin/bash", "-c", bash_command])

    def start(self) -> None:
        os.chdir(DOCKERFILES_DIR)

        docker.compose.up(detach=True)

    def report_status(self) -> None:
        server_url = self.get_crate_server_url()
        localhost_url = self.get_crate_server_localhost_url()
        print(f"The CRATE application is running at {server_url} "
              f"or {localhost_url}")

    def create_demo_data(self) -> None:
        dialect = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_ENGINE")
        user = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_USER_NAME")
        password = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_USER_PASSWORD")
        host = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_HOST")
        port = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_PORT")
        name = os.getenv("CRATE_DOCKER_SOURCE_DATABASE_NAME")

        url = self.get_sqlalchemy_url(dialect, user, password, host, port, name)

        self.run_crate_command(f"crate_make_demo_database {url}")

    def create_data_dictionary(self) -> None:
        data_dictionary = self.get_data_dictionary_filename()
        self.run_crate_command(f"crate_anonymise --draftdd > {data_dictionary}")

    def get_data_dictionary_filename(self) -> str:
        return "/crate/cfg/data_dictionary.tsv"

    def anonymise_demo_data(self) -> None:
        self.run_crate_command("crate_anonymise --full")

    def get_sqlalchemy_url(self,
                           dialect: str,
                           user: str,
                           password: str,
                           host: str,
                           port: str,
                           name: str) -> str:

        scheme = self.get_sqlalchemy_engine(dialect)
        netloc = f"{user}:{password}@{host}:{port}"
        path = name
        query = "charset=utf8"
        params = fragment = None

        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def get_sqlalchemy_engine(self, label: str) -> str:
        engines = {
            "mysql": "mysql+mysqldb",
            "oracle": "oracle+cxoracle",
            "postgresql": "postgresql+psycopg2",
        }

        return engines[label]

    def get_crate_server_url(self) -> str:
        if self.use_https():
            scheme = "https"
        else:
            scheme = "http"

        ip_address = self.get_crate_server_ip_from_host()

        netloc = f"{ip_address}:8000"
        path = self.get_crate_server_path()
        params = query = fragment = None

        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def get_crate_server_localhost_url(self) -> str:
        if self.use_https():
            scheme = "https"
        else:
            scheme = "http"

        port = self.get_crate_server_port_from_host()
        netloc = f"localhost:{port}"
        path = self.get_crate_server_path()
        params = query = fragment = None

        return urllib.parse.urlunparse(
            (scheme, netloc, path, params, query, fragment)
        )

    def use_https(self) -> bool:
        return os.getenv("CRATE_DOCKER_CRATEWEB_USE_HTTPS") == "1"

    def get_crate_server_path(self) -> str:
        return "/crate"

    def get_crate_server_ip_address(self) -> str:
        container = docker.container.inspect("crate_crate_server")
        network_settings = container.network_settings

        return network_settings.networks['crate_crateanon_network'].ip_address

    def get_crate_server_ip_from_host(self) -> str:
        raise NotImplementedError

    def get_crate_server_port_from_host(self) -> str:
        return os.getenv("CRATE_DOCKER_CRATEWEB_HOST_PORT")


class Wsl2Installer(Installer):
    def get_crate_server_ip_from_host(self) -> str:
        # ip -j -f inet -br addr show eth0
        # Also -p(retty) when debugging manually
        ip_info = json.loads(run(
            ["ip", "-j", "-f", "inet", "-br", "addr", "show", "eth0"],
            stdout=PIPE
        ).stdout.decode("utf-8"))

        ip_address = ip_info[0]["addr_info"][0]["local"]

        return ip_address


class NativeLinuxInstaller(Installer):
    def get_crate_server_ip_from_host(self) -> str:
        return self.get_crate_server_ip_address()


class MacOsInstaller(Installer):
    pass


def main() -> None:
    installer = get_installer()
    installer.install()


def get_installer() -> Installer:
    sys_info = uname()

    if "microsoft-standard" in sys_info.release:
        return Wsl2Installer()

    if sys_info.system == "Linux":
        return NativeLinuxInstaller()

    if sys_info.system == "Darwin":
        return MacOsInstaller()

    if sys_info.system == "Windows":
        print("The installer cannot be run under native Windows. Please "
              "install Windows Subsystem for Linux 2 (WSL2) and run the "
              "installer from there. Alternatively follow the instructions "
              "to install CRATE manually.")
        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()

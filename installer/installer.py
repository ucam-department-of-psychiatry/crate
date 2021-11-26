#!/usr/bin/env python

import os
import sys
import secrets
from typing import Optional

from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import input_dialog, message_dialog
from python_on_whales import docker

EXIT_FAILURE = 1

INSTALLER_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.join(INSTALLER_DIR, "..")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")
DOCKERFILES_DIR = os.path.join(DOCKER_DIR, "dockerfiles")


class Installer:
    def __init__(self) -> None:
        self.title = "CRATE Setup"
        self.testing = False

    def install(self) -> None:
        self.configure()
        self.create_local_settings()

    def configure(self) -> None:
        self.setenv(
            "CRATE_DOCKER_INSTALL_USER_ID",
            self.get_install_user_id()
        )
        self.setenv(
            "CRATE_DOCKER_INSTALL_GROUP_ID",
            self.get_install_group_id()
        )
        self.setenv(
            "CRATE_DOCKER_CONFIG_HOST_DIR",
            self.get_docker_config_host_dir()
        )
        self.setenv(
            "CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR",
            self.get_docker_gate_bioyodie_resources_host_dir()
        )
        self.setenv(
            "CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME",
            "crateweb_local_settings.py"
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_ROOT_PASSWORD",
            self.get_docker_mysql_root_password()
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
            self.get_docker_mysql_crate_user_password()
        )

    def get_install_user_id(self) -> str:
        return str(os.geteuid())

    def get_install_group_id(self) -> str:
        return str(os.getegid())

    def get_docker_config_host_dir(self) -> str:
        if self.testing:
            return "/home/martin/crate_config"

        return self.get_user_dir(
            "Select the directory where CRATE will store its configuration"
        )

    def get_docker_gate_bioyodie_resources_host_dir(self) -> str:
        if self.testing:
            return "/home/martin/bioyodie_config"

        return self.get_user_dir(
            "Select the directory where CRATE will store Bio-YODIE resources"
        )

    def get_docker_mysql_root_password(self) -> str:
        if self.testing:
            return "ramalamadingdong"

        return self.get_user_password(
            "Enter a new MySQL root password"
        )

    def get_docker_mysql_crate_user_password(self) -> str:
        if self.testing:
            return "shoobydoobydoo"

        return self.get_user_password(
            "Enter a new password for the MySQL user that CRATE will create"
        )

    def setenv(self, name: str, value: str) -> None:
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

    def get_user_input(self, text: str, title: Optional[str] = None) -> str:
        if title is None:
            title = self.title

        value = input_dialog(title=title, text=text).run()
        if value is None:
            sys.exit(EXIT_FAILURE)

        return value

    def create_local_settings(self) -> None:
        if not os.path.exists(self.local_settings_full_path()):
            os.chdir(DOCKERFILES_DIR)

            demo_config_command = ("source /crate/venv/bin/activate; "
                                   "crate_print_demo_crateweb_config > "
                                   "$CRATE_WEB_LOCAL_SETTINGS")

            docker.compose.run("crate_workers",
                               remove=True,
                               command=["/bin/bash",
                                        "-c",
                                        demo_config_command])

        self.configure_local_settings()

    def configure_local_settings(self) -> None:
        with open(self.local_settings_full_path(), "r") as f:
            settings = f.read()

        root_dir = "/crate"
        config_dir = os.path.join(root_dir, "cfg")
        archive_template_dir = os.path.join(config_dir, "archive_templates")
        tmp_dir = os.path.join(root_dir, "tmp")
        venv_dir = os.path.join(root_dir, "venv")
        crate_install_dir = os.path.join(venv_dir, "lib", "python3.6",
                                         "site-packages")

        replace_dict = {
            "archive_attachment_dir": os.path.join(config_dir,
                                                   "archive_attachments"),
            "archive_static_dir": os.path.join(archive_template_dir, "static"),
            "archive_template_cache_dir": os.path.join(
                tmp_dir, "archive_templates", "cache"
            ),
            "archive_template_dir": archive_template_dir,
            "broker_url": "amqp://rabbitmq:5672",
            "crate_install_dir": crate_install_dir,
            "django_site_root_absolute_url": "http://crate_server:8088",
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

        }

        for (search, replace) in replace_dict.items():
            settings = settings.replace(f"@@{search}@@", replace)

        with open(self.local_settings_full_path(), "w") as f:
            f.write(settings)


    def local_settings_full_path(self) -> str:
        return os.path.join(
            os.getenv("CRATE_DOCKER_CONFIG_HOST_DIR"),
            os.getenv("CRATE_DOCKER_CRATEWEB_CONFIG_FILENAME")
        )

def main() -> None:
    installer = Installer()
    installer.testing = True  # TODO remove
    installer.install()


if __name__ == "__main__":
    main()

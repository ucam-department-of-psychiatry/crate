#!/usr/bin/env python

import os
from pathlib import Path
import sys
from typing import Optional

from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import input_dialog, message_dialog, prompt
from python_on_whales import docker

EXIT_FAILURE = 1

INSTALLER_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.join(INSTALLER_DIR, "..")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")
DOCKERFILES_DIR = os.path.join(DOCKER_DIR, "dockerfiles")

HOME = str(Path.home())
CRATE_CONFIG_DIR = os.path.join(HOME, "crate_config")
CRATE_WEB_LOCAL_SETTINGS = os.path.join(CRATE_CONFIG_DIR,
                                        "crateweb_local_settings.py")


class Installer:
    def __init__(self) -> None:
        self.title = "CRATE Setup"
        self.testing = False

    def install(self) -> None:
        self.configure()
        self.create_local_settings()

    def configure(self) -> None:
        self.setenv(
            "CRATE_DOCKER_CONFIG_HOST_DIR",
            self.get_docker_config_host_dir()
        )
        self.setenv(
            "CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR",
            self.get_docker_gate_bioyodie_resources_host_dir()
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_ROOT_PASSWORD",
            self.get_docker_mysql_root_password()
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD",
            self.get_docker_mysql_crate_user_password()
        )

    def get_docker_config_host_dir(self) -> str:
        if self.testing:
            return "/c/Users/Martin/crate_config"

        return self.get_user_dir(
            "Select the directory where CRATE will store its configuration"
        )

    def get_docker_gate_bioyodie_resources_host_dir(self) -> str:
        if self.testing:
            return "/c/Users/Martin/bioyodie_config"

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
        os.chdir(DOCKERFILES_DIR)

        demo_config_command = ("source /crate/venv/bin/activate; "
                               "crate_print_demo_crateweb_config > "
                               f"{CRATE_WEB_LOCAL_SETTINGS}")

        docker.compose.run("crate_workers",
                           remove=True,
                           command=["/bin/bash",
                                    "-c",
                                    f'"{demo_config_command}"'])


def main() -> None:
    installer = Installer()
    installer.testing = True  # TODO remove
    installer.install()


if __name__ == "__main__":
    main()

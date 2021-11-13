#!/usr/bin/env python

import os
from pathlib import Path

from python_on_whales import docker
from urwid import Edit, ExitMainLoop, Filler, MainLoop

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
    def install(self) -> None:
        self.configure()
        self.create_local_settings()

    def configure(self) -> None:
        self.setenv(
            "CRATE_DOCKER_CONFIG_HOST_DIR",
            self.user_dir(
                "Select the directory where CRATE will store its configuration"
            )
        )
        self.setenv(
            "CRATE_DOCKER_GATE_BIOYODIE_RESOURCES_HOST_DIR",
            self.user_dir(
                "Select the directory where CRATE will store Bio-YODIE resources"
            )
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_ROOT_PASSWORD",
            self.user_input(
                "Enter a new MySQL root password"
            )
        )
        self.setenv(
            "CRATE_DOCKER_MYSQL_CRATE_USER_PASSWORD",
            self.user_input(
                "Enter a new password for the MySQL user that CRATE will create"
            )
        )

    def setenv(self, name: str, value: str) -> None:
        os.environ[name] = value

    def user_dir(self, prompt: str) -> str:
        # TODO: File browser
        return self.user_input(prompt)

    def user_input(self, prompt: str) -> str:
        edit = Edit(f"{prompt}\n")
        filler = Filler(edit)
        loop = MainLoop(filler, unhandled_input=self.exit_on_enter)
        loop.run()

        return edit.edit_text

    @staticmethod
    def exit_on_enter(key: str) -> None:
        if key == "enter":
            raise ExitMainLoop()

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
    installer.install()


if __name__ == "__main__":
    main()

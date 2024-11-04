#!/usr/bin/env python

# installer/installer_boot.py

# ==============================================================================
#
#     Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
#     Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
#
#     This file is part of CRATE.
#
#     CRATE is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     CRATE is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with CRATE. If not, see <https://www.gnu.org/licenses/>.
#
# ==============================================================================

# Installs CRATE running under Docker with demonstration databases.
# This script does the minimum necessary to fetch and
# run the main installer.py script. It runs from the default system python
# executable and has no third-party dependencies.

# Do as little as possible in this script.
# Do as much as possible in installer.py.

# - Prerequisites for Windows:
#   - Install WSL2
#   - Install Docker Desktop for Windows
#   - Enable WSL2 in Docker Desktop
#
# - Prerequisites for Ubuntu:
#     sudo apt-get update
#     sudo apt -y install python3-virtualenv python3-venv

# When called with no arguments, the installation process is as in docker.rst
# With the -- (development) option, the installer runs on the local copy of the
# source code.

from argparse import ArgumentParser
from dataclasses import dataclass
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional
import urllib.request
from venv import EnvBuilder

EXIT_SUCCESS = 0  # No error
EXIT_FAILURE = 1  # Unexpected error
EXIT_USER = 2  # User error e.g bad command, misconfiguration, CTRL-C


class Command:
    INSTALL = "install"
    STOP = "stop"


@dataclass
class InstallerBoot:
    command: str
    github_repository: str
    crate_root_dir: str
    light_mode: bool
    run_locally: bool
    recreate_venv: bool
    version: Optional[str]
    update: bool
    verbose: bool

    def __post_init__(self) -> None:
        self.repository_url = f"https://github.com/{self.github_repository}"
        self.src_dir = os.path.join(self.crate_root_dir, "src")
        self.venv_dir = os.path.join(self.crate_root_dir, "venv")
        self.venv_python = os.path.join(self.venv_dir, "bin", "python")
        self.installer_dir = self.get_installer_dir()

    def get_installer_dir(self) -> str:
        if self.run_locally:
            return os.path.dirname(os.path.realpath(__file__))

        return os.path.join(self.src_dir, "installer")

    def boot(self) -> None:
        self.ensure_root_dir_exists()
        if not self.run_locally:
            self.checkout_code()

        if self.recreate_venv or not os.path.exists(self.venv_dir):
            self.create_virtual_environment()
            self.install_requirements()

        self.run_installer()

    def ensure_root_dir_exists(self) -> None:
        try:
            Path(self.crate_root_dir).mkdir(parents=True, exist_ok=True)
        except OSError:
            username = getpass.getuser()

            print(
                f"Failed to create the directory {self.crate_root_dir}. This "
                "may be because the user '{username}' does not have write "
                "access to it. If this is the case, this might also be a good "
                "opportunity to create a common group for all CRATE users.\n\n"
                "For example (Ubuntu):\n"
                "sudo groupadd crate\n"
                f"sudo usermod -aG crate {username}\n"
                "sudo usermod -aG crate anotheruser\n"
                "sudo mkdir {self.crate_root_dir}\n"
                f"sudo chown -R {username}:crate {self.crate_root_dir}\n\n"
                "Then logout and log back in again or:\n"
                "su -u {username}\n"
                "for the installer to pick up the new group."
            )

            raise

    def checkout_code(self) -> None:
        if not os.path.exists(self.src_dir):
            os.chdir(self.crate_root_dir)
            subprocess.run(
                ["git", "clone", self.repository_url, self.src_dir], check=True
            )

        os.chdir(self.src_dir)
        subprocess.run(["git", "fetch"], check=True)

        if self.version is None:
            self.version = self.get_commit_of_latest_release()

        subprocess.run(["git", "checkout", self.version], check=True)

    def get_commit_of_latest_release(self) -> str:
        api_url = (
            "https://api.github.com/"
            f"repos/{self.github_repository}/releases/latest"
        )

        with urllib.request.urlopen(api_url) as response:
            latest_release = json.loads(response.read().decode("utf-8"))

        return latest_release["tag_name"]

    def create_virtual_environment(self) -> None:
        builder = EnvBuilder(
            clear=self.recreate_venv, with_pip=True, upgrade_deps=True
        )

        builder.create(self.venv_dir)

    def install_requirements(self) -> None:
        subprocess.run(
            [
                self.venv_python,
                "-m",
                "pip",
                "install",
                "-r",
                f"{self.installer_dir}/installer_requirements.txt",
            ],
            check=True,
        )

    def run_installer(self) -> None:
        installer_args = [
            self.venv_python,
            f"{self.installer_dir}/installer.py",
            "--crate_root_dir",
            self.crate_root_dir,
        ]

        if self.update:
            installer_args.append("--update")

        if self.verbose:
            installer_args.append("--verbose")

        if self.light_mode:
            installer_args.append("--light_mode")

        installer_args.append(self.command)

        returned_value = subprocess.run(installer_args)
        if returned_value.return_code in (EXIT_SUCCESS, EXIT_USER):
            return

        sys.exit(returned_value.return_code)


def main() -> None:
    if not (sys.version_info.major >= 3 and sys.version_info.minor >= 9):
        print(sys.version_info)
        print(
            "You need at least Python 3.9 to run the installer.",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)

    parser = ArgumentParser()
    parser.add_argument(
        "--github_repository",
        default="ucam-department-of-psychiatry/crate",
        help="Install CRATE from this GitHub repository",
    )
    parser.add_argument(
        "--crate_root_dir",
        help=(
            "Directory in which to place the files required by CRATE and, "
            "unless the --run_locally argument is specified, download the "
            "CRATE source."
        ),
        default=os.getenv("CRATE_INSTALLER_CRATE_ROOT_HOST_DIR"),
    )
    parser.add_argument(
        "--light_mode",
        action="store_true",
        default=False,
        help="Use this if your terminal has a light background",
    )
    parser.add_argument(
        "--run_locally",
        action="store_true",
        default=False,
        help=(
            "Do not fetch the CRATE source from GitHub. Assume this "
            "script is run from an existing checkout of CRATE "
            "and the CRATE source can be found relative to this file."
        ),
    )
    parser.add_argument(
        "--recreate_venv",
        action="store_true",
        help="Recreate the CRATE installer virtual environment",
    )
    parser.add_argument(
        "--version",
        help=(
            "Use this commit/tag/branch of CRATE. If unset, use the latest "
            "stable release."
        ),
        default=None,
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rebuild the CRATE Docker image",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Be verbose",
        default=False,
    )
    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid CRATE installer commands are:",
        help="Specify one command.",
        dest="command",
    )
    subparsers.add_parser(
        Command.INSTALL,
        help=(
            "Install CRATE into a Docker Compose environment. Default if not "
            "specified."
        ),
    )
    subparsers.add_parser(
        Command.STOP, help="Stop the Docker Compose application."
    )
    parser.set_defaults(command=Command.INSTALL)

    args = parser.parse_args()

    if args.crate_root_dir is None:
        print(
            "You must specify --crate_root_dir or set the environment "
            "variable CRATE_INSTALLER_CRATE_ROOT_DIR"
        )

        sys.exit(EXIT_USER)

    boot = InstallerBoot(**vars(args))
    boot.boot()


if __name__ == "__main__":
    main()

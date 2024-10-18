#!/usr/bin/env python

# installer/installer_bootstrap.py

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
import os
import shutil
import subprocess
import sys
import urllib.request
from venv import EnvBuilder

EXIT_FAILURE = 1


class Command:
    INSTALL = "install"
    STOP = "stop"


@dataclass
class InstallerBoot:
    command: str
    github_repository: str
    installer_root_dir: str
    no_fetch: bool
    recreate_venv: bool
    release_version: str
    update: bool
    venv_dir: str
    verbose: bool

    def __post_init__(self) -> None:
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        path = f"releases/download/{self.release_version}"
        self.release_url = f"{self.github_repository}/{path}"
        self.venv_python = os.path.join(self.venv_dir, "bin", "python")

    def boot(self) -> None:
        if not self.no_fetch:
            self.download_release_file("installer.py")
            self.download_release_file("installer_requirements.txt")

        if self.recreate_venv or not os.path.exists(self.venv_dir):
            self.create_virtual_environment()
            self.install_requirements()

        self.run_installer()

    def create_virtual_environment(self) -> None:
        builder = EnvBuilder(clear=self.recreate_venv, with_pip=True)

        builder.create(self.venv_dir)
        builder.upgrade_dependencies()

    def delete_virtualenv(self) -> None:
        shutil.rmtree(self.venv_dir, ignore_errors=True)

    def download_release_file(self, filename: str) -> None:
        self.download(
            f"{self.release_url}/{filename}",
            f"{self.installer_root_dir}/{filename}",
        )

    def download(self, url: str, filename: str) -> None:
        print(f"Downloading {url} to {filename}...")
        with urllib.request.urlopen(url) as response, open(
            filename, "wb"
        ) as out_file:
            shutil.copyfileobj(response, out_file)

    def install_requirements(self) -> None:
        subprocess.run(
            [
                self.venv_python,
                "-m",
                "pip",
                "install",
                "-r",
                f"{self.installer_root_dir}/installer_requirements.txt",
            ],
            check=True,
        )

    def run_installer(self) -> None:
        installer_args = [
            self.venv_python,
            f"{self.installer_root_dir}/installer.py",
        ] + [self.command]

        subprocess.run(installer_args, check=True)


def main() -> None:
    if not (sys.version_info.major >= 3 and sys.version_info.minor >= 9):
        print(sys.version_info)
        print(
            "You need at least Python 3.9 to run the installer.",
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)

    home_dir = os.path.expanduser("~")

    parser = ArgumentParser()
    parser.add_argument(
        "--github_repository",
        default="https://github.com/ucam-department-of-psychiatry/crate",
        help="Install CRATE from this GitHub repository",
    )
    parser.add_argument(
        "--installer_root_dir",
        default=os.path.join(home_dir, "crate_installer"),
        help="Directory in which to download the installer scripts",
    )
    parser.add_argument(
        "--no_fetch",
        action="store_true",
        help="Do not fetch files from GitHub. Use local installation",
    )
    parser.add_argument(
        "--release_version",
        help="Install this release of CRATE",
        default="latest",
    )
    parser.add_argument(
        "--recreate_venv",
        action="store_true",
        help="Recreate the CRATE installer virtual environment",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update the existing CRATE installation",
        default=False,
    )
    parser.add_argument(
        "--venv_dir",
        default=os.path.join(home_dir, ".virtualenvs", "crate_installer"),
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
        help="Install CRATE into a Docker Compose environment.",
    )
    subparsers.add_parser(
        Command.STOP, help="Stop the Docker Compose application."
    )
    parser.set_defaults(command=Command.INSTALL)

    args = parser.parse_args()

    boot = InstallerBoot(**vars(args))
    boot.boot()


if __name__ == "__main__":
    main()

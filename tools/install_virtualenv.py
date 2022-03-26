#!/usr/bin/env python
# ... unusual shebang; need system Python 3

"""
tools/install_virtualenv.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Installs a virtual environment.

"""

import argparse
import os
import platform
import subprocess
import sys
from typing import List


assert sys.version_info >= (3, 7), "Need Python 3.7+"

LINUX = platform.system() == 'Linux'
# LINUX_DIST = platform.linux_distribution()[0].lower()
# DEB = LINUX_DIST in ['ubuntu', 'debian']
# RPM = LINUX_DIST in ['fedora', 'rhel', 'centos']

DESCRIPTION = """
Make a new virtual environment.
Please specify the directory in which the virtual environment should be
created. For example, for a testing environment
    {script} ~/crate_virtualenv

or for a production environment:
    sudo --user=www-data XDG_CACHE_HOME=/usr/share/crate/.cache \\
        {script} /usr/share/crate/virtualenv
""".format(script=os.path.basename(__file__))  # noqa

PYTHON = sys.executable  # Windows needs this before Python executables
PYTHONBASE = os.path.basename(PYTHON)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
# PIP_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements.txt')
# DEB_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements-ubuntu.txt')
# RPM_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements-rpm.txt')

SEP = "=" * 79


def title(msg: str) -> None:
    """
    Prints a title.
    """
    print(SEP)
    print(msg)
    print(SEP)


def cmd_returns_zero_success(cmdargs: List[str]) -> bool:
    """
    Runs a command; returns True if it succeeded and False if it failed.
    """
    print(f"Checking result of command: {cmdargs}")
    try:
        subprocess.check_call(cmdargs)
        return True
    except subprocess.CalledProcessError:
        return False


def check_call(cmdargs: List[str]) -> None:
    """
    Displays its intent, executes a command, and checks that it succeeded.
    """
    print(f"Command: {cmdargs}")
    subprocess.check_call(cmdargs)


def main() -> None:
    """
    Create a virtual environment. See DESCRIPTION.
    """
    if not LINUX:
        raise AssertionError("Installation requires Linux.")
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("virtualenv", help="New virtual environment directory")
    parser.add_argument("package", help="New package directory/tgz")
    parser.add_argument("--virtualenv_minimum_version", default="13.1.2",
                        help="Minimum version of virtualenv tool")
    # parser.add_argument("--skippackagechecks", action="store_true",
    #                     help="Skip verification of system packages (use this "
    #                          "when calling script from a yum install, for "
    #                          "example).")
    args = parser.parse_args()

    venv_tool = 'virtualenv'
    venv_python = os.path.join(args.virtualenv, 'bin', 'python')
    venv_pip = os.path.join(args.virtualenv, 'bin', 'pip')
    activate = "source " + os.path.join(args.virtualenv, 'bin', 'activate')

    print(f"XDG_CACHE_HOME: {os.environ.get('XDG_CACHE_HOME', None)}")
    # if not args.skippackagechecks:
    #     if DEB:
    #         title("Prerequisites, from " + DEB_REQ_FILE)
    #         packages = get_lines_without_comments(DEB_REQ_FILE)
    #         for package in packages:
    #             require_deb(package)
    #     # elif RPM:
    #     #     title("Prerequisites, from " + RPM_REQ_FILE)
    #     #     packages = get_lines_without_comments(RPM_REQ_FILE)
    #     #     for package in packages:
    #     #         require_rpm(package)
    #     else:
    #         raise AssertionError("Not DEB; don't know what to do")
    #     print('OK')

    title(f"Ensuring virtualenv is installed for system Python ({PYTHON})")
    check_call([PYTHON, '-m', 'pip', 'install',
                f'virtualenv>={args.virtualenv_minimum_version}'])
    print('OK')

    title(f"Using system Python ({PYTHON}) and virtualenv ({venv_tool}) "
          f"to make {args.virtualenv}")
    check_call([PYTHON, '-m', venv_tool, args.virtualenv])
    print('OK')

    title("Upgrading virtualenv pip, if required")
    check_call([venv_pip, 'install', '--upgrade', 'pip'])

    title("Checking version of tools within new virtualenv")
    print(venv_python)
    check_call([venv_python, '--version'])
    print(venv_pip)
    check_call([venv_pip, '--version'])

    title("Use pip within the new virtualenv to install package")
    check_call([venv_pip, 'install', args.package])
    print('OK')
    print('--- Virtual environment installed successfully')

    print(f"To activate the virtual environment, use\n"
          f"    {activate}\n\n")


if __name__ == "__main__":
    main()

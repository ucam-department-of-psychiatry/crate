#!/usr/bin/env python3

import argparse
import os
import platform
# import shutil
import subprocess
import sys

# from crate_anon.common.fileops import get_lines_without_comments


if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")
LINUX = platform.system() == 'Linux'
LINUX_DIST = platform.linux_distribution()[0].lower()
DEB = LINUX_DIST in ['ubuntu', 'debian']
RPM = LINUX_DIST in ['fedora', 'rhel', 'centos']

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
PIP_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements.txt')
DEB_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements-ubuntu.txt')
# RPM_REQ_FILE = os.path.join(PROJECT_BASE_DIR, 'requirements-rpm.txt')

SEP = "=" * 79


def title(msg):
    print(SEP)
    print(msg)
    print(SEP)


def cmd_returns_zero_success(cmdargs):
    print("Checking result of command: {}".format(cmdargs))
    try:
        subprocess.check_call(cmdargs)
        return True
    except subprocess.CalledProcessError:
        return False


def check_call(cmdargs):
    print("Command: {}".format(cmdargs))
    subprocess.check_call(cmdargs)


def require_deb(package):
    if cmd_returns_zero_success(['dpkg', '-l', package]):
        return
    print("You must install the package {package}. On Ubuntu, use the command:"
          "\n"
          "    sudo apt-get install {package}".format(package=package))
    sys.exit(1)


# def require_rpm(package):
#     # PROBLEM: can't call yum inside yum. See --skippackagechecks option.
#     if cmd_returns_zero_success(['yum', 'list', 'installed', package]):
#         return
#     print("You must install the package {package}. On CentOS, use the command:"  # noqa
#           "\n"
#           "    sudo yum install {package}".format(package=package))
#     sys.exit(1)


if __name__ == '__main__':
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

    VENV_TOOL = 'virtualenv'
    VENV_PYTHON = os.path.join(args.virtualenv, 'bin', 'python')
    VENV_PIP = os.path.join(args.virtualenv, 'bin', 'pip')
    ACTIVATE = "source " + os.path.join(args.virtualenv, 'bin', 'activate')

    print("XDG_CACHE_HOME: {}".format(os.environ.get('XDG_CACHE_HOME',
                                                     None)))
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

    title("Ensuring virtualenv is installed for system"
          " Python ({})".format(PYTHON))
    check_call([PYTHON, '-m', 'pip', 'install',
                'virtualenv>={}'.format(args.virtualenv_minimum_version)])
    print('OK')

    title("Using system Python ({}) and virtualenv ({}) to make {}".format(
          PYTHON, VENV_TOOL, args.virtualenv))
    check_call([PYTHON, '-m', VENV_TOOL, args.virtualenv])
    print('OK')

    title("Upgrading virtualenv pip, if required")
    check_call([VENV_PIP, 'install', '--upgrade', 'pip'])

    title("Checking version of tools within new virtualenv")
    print(VENV_PYTHON)
    check_call([VENV_PYTHON, '--version'])
    print(VENV_PIP)
    check_call([VENV_PIP, '--version'])

    title("Use pip within the new virtualenv to install package")
    check_call([VENV_PIP, 'install', args.package])
    print('OK')
    print('--- Virtual environment installed successfully')

    print("To activate the virtual environment, use\n"
          "    {ACTIVATE}\n\n".format(ACTIVATE=ACTIVATE))

#!/usr/bin/env python

"""
crate_anon/common/dockerfunc.py

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

**Docker assistance functions.**

"""

from dataclasses import dataclass
import logging
import subprocess
import urllib.parse
from typing import Dict, List, Union

from cardinal_pythonlib.fileops import relative_filename_within_dir

from crate_anon.common.constants import DockerConstants

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_DOCKER_CMD = "docker"


# =============================================================================
# Helper functions to operate within Docker
# =============================================================================


def warn_if_not_within_docker_dir(
    param_name: str,
    filespec: str,
    permit_cfg: bool = False,
    permit_venv: bool = False,
    permit_tmp: bool = False,
    param_contains_not_is: bool = False,
    is_env_var: bool = False,
    as_file_url: bool = False,
) -> None:
    """
    If the specified filename isn't within a relevant directory that will be
    used by CRATE when operating within a Docker Compose application, warn
    the user.

    Args:
        param_name:
            Name of the parameter in the CRATE config file.
        filespec:
            Filename (or filename-like thing) to check.
        permit_cfg:
            Permit the file to be in the configuration directory.
        permit_venv:
            Permit the file to be in the virtual environment directory.
        permit_tmp:
            Permit the file to be in the shared temporary space.
        param_contains_not_is:
            The parameter "contains", not "is", the filename.
        is_env_var:
            The parameter is an environment variable.
        as_file_url:
            filespec is a "file://" URL, rather than a filename
    """
    if not filespec:
        return
    if as_file_url:
        filepath = urllib.parse.urlparse(filespec).path
    else:
        filepath = filespec
    param_descriptor = (
        "Environment variable" if is_env_var else "Config parameter"
    )
    is_phrase = "contains" if param_contains_not_is else "is"
    permitted_dirs = []  # type: List[str]
    if permit_cfg:
        permitted_dirs.append(DockerConstants.CONFIG_DIR)
    if permit_venv:
        permitted_dirs.append(DockerConstants.VENV_DIR)
    if permit_tmp:
        permitted_dirs.append(DockerConstants.TMP_DIR)
    ok = any(relative_filename_within_dir(filepath, d) for d in permitted_dirs)
    if not ok:
        log.warning(
            f"{param_descriptor} {param_name} {is_phrase} {filespec!r}, "
            f"which is not within the permitted Docker directories "
            f"{permitted_dirs!r}"
        )


# =============================================================================
# Helper functions to fire up Docker containers, for testing
# =============================================================================


@dataclass
class VolumeMount:
    """
    Represents a bind mount (mounting a host directory within Docker).
    """

    host_dir: str
    docker_dir: str
    rw: bool = False  # read/write, not read only?

    def __post_init__(self) -> None:
        """
        Validation.
        """
        # ---------------------------------------------------------------------
        # Host
        # ---------------------------------------------------------------------
        if ":" in self.host_dir:
            raise ValueError(
                f"Host directory should not contain ':' but is {self.host_dir}"
            )
        if not self.host_dir.startswith("/"):
            raise ValueError(
                f"Host directory should start with '/' but is "
                f"{self.host_dir}"
            )
        if self.rw and self.host_dir == "/":
            raise ValueError(
                "It is too dangerous to mount the host root directory "
                "read-write"
            )
        # ---------------------------------------------------------------------
        # Docker
        # ---------------------------------------------------------------------
        if ":" in self.docker_dir:
            raise ValueError(
                f"Docker directory should not contain ':' but is "
                f"{self.docker_dir}"
            )
        if not self.docker_dir.startswith("/"):
            raise ValueError(
                f"Docker directory should start with '/' but is "
                f"{self.docker_dir}"
            )

    def switch(self) -> str:
        """
        Returns the Docker switch for the mount.
        """
        flag = "rw" if self.rw else "ro"
        return f"--volume={self.host_dir}:{self.docker_dir}:{flag}"

    def description(self) -> str:
        """
        Returns a human-readable description.
        """
        flag = "read/write" if self.rw else "read only"
        return (
            f"Mounting host directory {self.host_dir!r} as "
            f"{self.docker_dir!r} inside Docker ({flag})"
        )


def run_subprocess(cmdargs: List[str]) -> None:
    """
    Run a command.
    """
    log.debug(cmdargs)
    subprocess.check_call(cmdargs)


def docker_build(
    dockerfile: str,
    tag: str,
    context: str,
    build_args: Dict[str, str] = None,
    docker_cmd: str = DEFAULT_DOCKER_CMD,
) -> None:
    """
    Build a Docker container from a Dockerfile.

    In 2024, on Ubuntu 22.02, you may see:

    .. code-block:: none

        DEPRECATED: The legacy builder is deprecated and will be removed in a future release.
                Install the buildx component to build images with BuildKit:
                https://docs.docker.com/go/buildx/

    This just requires ``sudo apt-get install docker-buildx``, and then the
    ``docker build`` command works as before, but is prettier.

    """  # noqa: E501
    cmdargs = [
        docker_cmd,
        "build",
        # Build a Docker image if necessary. It's slow the first time but then
        # very quick thereafter (it won't rebuild unless the Dockerfile
        # changes).
        "--file",
        dockerfile,
        # Specifies a named Docker file. It's optional because our Docker file
        # is the default of "Dockerfile", but never mind.
        "--tag",
        tag,
        # Give the image this tag (or optionally, name:tag).
        context
        # The context is the top-level directory used for building the Docker
        # image. All files used by COPY must be within the context.
    ]
    if build_args:
        for k, v in build_args.items():
            if "=" in k:
                raise ValueError(
                    f"Don't use build_arg (ARG) variables with '=' in their "
                    f"name; you used {k!r}"
                )
            cmdargs += ["--build-arg", f"{k}={v}"]
    run_subprocess(cmdargs)


def docker_run(
    image: str,
    cmd: Union[str, List[str]] = None,
    interactive: bool = False,
    rm: bool = True,
    mounts: List[VolumeMount] = None,
    envvars: Dict[str, str] = None,
    ports_docker_to_host: Dict[int, int] = None,
    user: str = None,
    workdir: str = None,
    network: str = None,
    network_alias: str = None,
    name: str = None,
    docker_cmd: str = DEFAULT_DOCKER_CMD,
    daemon: bool = False,
) -> None:
    """
    Run a command in the Docker environment (in a pre-built container).
    """
    cmd = cmd or []
    if isinstance(cmd, str):
        cmd = [cmd]
    mounts = mounts or []
    envvars = envvars or {}
    ports_docker_to_host = ports_docker_to_host or {}

    cmdargs = [
        docker_cmd,
        "run"
        # Run a command.
    ]
    for mount in mounts:
        cmdargs.append(mount.switch())
        log.info(mount.description())
    for var, value in envvars.items():
        # Set an environment variable. Use "-e" or "--env"
        cmdargs += ["--env", f"{var}={value}"]
    for docker_port, host_port in ports_docker_to_host.items():
        # Publish container's DOCKER_PORT so it can be seen on the host via
        # HOST_PORT. Use "-p" or "--publish". Implicitly adds "--expose".
        cmdargs += ["--publish", f"{host_port}:{docker_port}"]
    if name:
        cmdargs += ["--name", name]
    if network:
        cmdargs += ["--network", network]
        if network_alias:
            cmdargs += ["--network-alias", network_alias]
    if interactive:
        # Interact with user. Use "-it" or:
        cmdargs += ["--interactive", "--tty"]
    if rm:
        # Remove container afterwards (stops hard disk clogging up).
        cmdargs.append("--rm")
    if user:
        cmdargs += ["--user", user]
    if workdir:
        cmdargs += ["--workdir", workdir]
    if daemon:
        cmdargs += ["--detach"]  # or "-d"
    cmdargs.append(image)  # Image to run with
    cmdargs += cmd
    # If the command is missing, the image's default command is run.
    run_subprocess(cmdargs)

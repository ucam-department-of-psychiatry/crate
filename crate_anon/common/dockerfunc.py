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

crate_anon/crateweb/config/settings.py
**Docker assistance functions.**
"""

import logging
import urllib.parse
from typing import List

from cardinal_pythonlib.fileops import relative_filename_within_dir

from crate_anon.common.constants import DockerConstants

log = logging.getLogger(__name__)


# =============================================================================
# Helper functions
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

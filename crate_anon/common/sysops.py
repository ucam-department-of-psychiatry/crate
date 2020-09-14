#!/usr/bin/env python

"""
crate_anon/common/sysops.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Simple system operations.**

"""

import logging
import subprocess
import sys
from typing import List, Optional

log = logging.getLogger(__name__)


def die(msg: str, log_level: int = logging.CRITICAL,
        exit_code: int = 1) -> None:
    """
    Prints a message and hard-exits the program.

    Args:
        msg: message
        log_level: log level to use
        exit_code: exit code (errorlevel)
    """
    log.log(level=log_level, msg=msg)
    sys.exit(exit_code)


def check_call_verbose(args: List[str],
                       log_level: Optional[int] = logging.INFO) -> None:
    """
    Prints a copy/paste-compatible version of a command, then runs it.

    Args:
        args: command arguments
        log_level: log level

    Raises:
        :exc:`CalledProcessError` on external command failure
    """
    if log_level is not None:
        cmd_as_text = subprocess.list2cmdline(args)
        log.log(level=log_level, msg=cmd_as_text)
    subprocess.check_call(args)

#!/usr/bin/env python

"""
crate_anon/common/exceptions.py

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

**Exception-handling functions.**

"""

import logging
import sys
import traceback
from typing import Callable

from crate_anon.common.constants import EXIT_FAILURE, EXIT_SUCCESS

log = logging.getLogger(__name__)


def report_exception(exc: Exception) -> None:
    """
    Prints a critical exception nicely to the log.

    Args:
        exc: the exception
    """
    log.critical(exc)  # the exception message
    # log.critical(exc, exc_info=True)  # message + traceback
    traceback_msg = "".join(traceback.format_exception(
        None,  # etype: ignored
        exc,
        exc.__traceback__
    ))  # https://www.python.org/dev/peps/pep-3134/
    log.error(traceback_msg)


def call_main_with_exception_reporting(main_function: Callable) -> None:
    try:
        result = main_function()
        if isinstance(result, int):
            sys.exit(result)
        else:
            sys.exit(EXIT_SUCCESS)
    except Exception as exc:
        report_exception(exc)
        sys.exit(EXIT_FAILURE)

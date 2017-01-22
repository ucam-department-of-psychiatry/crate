#!/usr/bin/env python
# crate_anon/anonymise/logsupport.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

import logging
from typing import List

from colorlog import ColoredFormatter

from crate_anon.anonymise.constants import LOG_COLORS, LOG_DATEFMT


def get_colour_handler(extranames: List[str] = None) -> logging.StreamHandler:
    extras = ":" + ":".join(extranames) if extranames else ""
    fmt = (
        "%(cyan)s%(asctime)s.%(msecs)03d %(name)s{extras}:%(levelname)s: "
        "%(log_color)s%(message)s"
    ).format(extras=extras)
    cf = ColoredFormatter(
        fmt,
        datefmt=LOG_DATEFMT,
        reset=True,
        log_colors=LOG_COLORS,
        secondary_log_colors={},
        style='%'
    )
    ch = logging.StreamHandler()
    ch.setFormatter(cf)
    return ch


def configure_logger_for_colour(log: logging.Logger,
                                level: int = logging.INFO,
                                remove_existing: bool = False,
                                extranames: List[str] = None) -> None:
    """
    Applies a preconfigured datetime/colour scheme to a logger.
    Should ONLY be called from the "if __name__ == 'main'" script:
        https://docs.python.org/3.4/howto/logging.html#library-config
    """
    if remove_existing:
        log.handlers = []  # http://stackoverflow.com/questions/7484454
    log.addHandler(get_colour_handler(extranames))
    log.setLevel(level)


def main_only_quicksetup_rootlogger(level: int = logging.DEBUG) -> None:
    # Nasty. Only call from "if __name__ == '__main__'" clauses!
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level)
    logging.basicConfig(level=logging.DEBUG)

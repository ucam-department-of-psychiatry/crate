#!/usr/bin/env python

import logging

from colorlog import ColoredFormatter

from crate_anon.anonymise.constants import LOG_COLORS, LOG_DATEFMT


def get_colour_handler(extranames=None):
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


def configure_logger_for_colour(log, level=logging.INFO, remove_existing=False,
                                extranames=None):
    """
    Applies a preconfigured datetime/colour scheme to a logger.
    Should ONLY be called from the "if __name__ == 'main'" script:
        https://docs.python.org/3.4/howto/logging.html#library-config
    """
    if remove_existing:
        log.handlers = []  # http://stackoverflow.com/questions/7484454
    log.addHandler(get_colour_handler(extranames))
    log.setLevel(level)

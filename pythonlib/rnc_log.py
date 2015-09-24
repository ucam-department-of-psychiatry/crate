#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for logging.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 26 Feb 2015
Last update: 24 Sep 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

MOST OF THIS IS REDUNDANT.
SEE BETTER ADVICE AT:
    http://pieces.openpolitics.com/2012/04/python-logging-best-practices/
IN SUMMARY, LIBRARIES SHOULD DO THIS:
    import logging
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    # ... and log away
APPLICATIONS SHOULD DO THIS:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig()
OR THIS SORT OF THING:
    import logging
    logger = logging.getLogger(__name__)
    LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=logging.DEBUG)
    # ... and log away
"""

import logging


def remove_all_logger_handlers(logger):
    """Remove all handlers from a logger."""
    while logger.handlers:
        h = logger.handlers[0]
        logger.removeHandler(h)


def reset_logformat(logger, fmt, datefmt='%Y-%m-%d %H:%M:%S'):
    """Create a new formatter and apply it to the logger."""
    # logging.basicConfig() won't reset the formatter if another module
    # has called it, so always set the formatter like this.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    handler.setFormatter(formatter)
    remove_all_logger_handlers(logger)
    logger.addHandler(handler)
    logger.propagate = False


def reset_logformat_timestamped(logger, extraname="", level=logging.INFO):
    """Apply a simple time-stamped log format to an existing logger, and set
    its loglevel to either DEBUG or INFO."""
    namebit = extraname + ":" if extraname else ""
    fmt = ("%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:" + namebit +
           "%(message)s")
    # logger.info(fmt)
    reset_logformat(logger, fmt=fmt)
    # logger.info(fmt)
    logger.setLevel(level)

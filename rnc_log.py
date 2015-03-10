#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for logging.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 26 Feb 2015
Last update: 26 Feb 2015

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
"""

import logging


def remove_all_logger_handlers(logger):
    while logger.handlers:
        h = logger.handlers[0]
        logger.removeHandler(h)


def reset_logformat(logger, fmt):
    # logging.basicConfig() won't reset the formatter if another module
    # has called it, so always set the formatter like this.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(fmt=fmt)
    handler.setFormatter(formatter)
    remove_all_logger_handlers(logger)
    logger.addHandler(handler)
    logger.propagate = False

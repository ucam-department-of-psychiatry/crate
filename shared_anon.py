#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Shared functions for anonymiser.py, nlp_manager.py, webview_anon.py

Author: Rudolf Cardinal
Created at: 26 Feb 2015
Last update: 19 Mar 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

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

from rnc_crypto import MD5Hasher
from rnc_db import (
    is_valid_field_name,
    is_valid_table_name,
)


# =============================================================================
# Constants
# =============================================================================

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit
ENCRYPTED_OUTPUT_LENGTH = len(MD5Hasher("dummysalt").hash(MAX_PID_STR))
SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(ENCRYPTED_OUTPUT_LENGTH)
# ... in practice: VARCHAR(32)


# =============================================================================
# Validation
# =============================================================================

def ensure_valid_field_name(f):
    if not is_valid_field_name(f):
        raise ValueError("Field name invalid: {}".format(f))


def ensure_valid_table_name(f):
    if not is_valid_table_name(f):
        raise ValueError("Table name invalid: {}".format(f))


# =============================================================================
# Config
# =============================================================================

def read_config_string_options(obj, parser, section, options,
                               enforce_str=False):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            value = parser.get(section, o)
            setattr(obj, o, str(value) if enforce_str else value)
        else:
            setattr(obj, o, None)


def read_config_multiline_options(obj, parser, section, options):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            multiline = parser.get(section, o)
            values = [x.strip() for x in multiline.splitlines() if x.strip()]
            setattr(obj, o, values)
        else:
            setattr(obj, o, [])

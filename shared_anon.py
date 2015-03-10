#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Shared functions for anonymiser.py and nlp_manager.py

Author: Rudolf Cardinal
Created at: 26 Feb 2015
Last update: 03 Mar 2015

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

import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")

from rnc_crypto import MD5Hasher
import rnc_db
from rnc_db import (
    is_valid_field_name,
    is_valid_table_name
)
import rnc_log



# =============================================================================
# Constants
# =============================================================================

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit
# ENCRYPTED_OUTPUT_LENGTH = len(AESCipher("dummykey").encrypt(MAX_PID_STR))
ENCRYPTED_OUTPUT_LENGTH = len(MD5Hasher("dummysalt").hash(MAX_PID_STR))
SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(ENCRYPTED_OUTPUT_LENGTH)
# ... in practice: VARCHAR(32)


# =============================================================================
# Config/databases
# =============================================================================

def read_config_string_options(obj, parser, section, options,
                               enforce_str=False):
    if not parser.has_section(section):
        raise Exception("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            value = parser.get(section, o)
            enforce_str
            setattr(obj, o, str(value) if enforce_str else value)
        else:
            setattr(obj, o, None)


class DatabaseConfig(object):
    def __init__(self, parser, section):
        read_config_string_options(self, parser, section, [
            "engine",
            "host",
            "port",
            "user",
            "password",
            "db",
        ])
        self.port = int(self.port)
        self.check_valid(section)

    def check_valid(self, section):
        if not self.engine:
            raise Exception(
                "Database {} doesn't specify engine".format(section))
        self.engine = self.engine.lower()
        if self.engine not in ["mysql", "sqlserver"]:
            raise Exception("Unknown database engine: {}".format(self.engine))
        if self.engine == "mysql":
            if (not self.host or not self.port or not self.user or not
                    self.password or not self.db):
                raise Exception("Missing MySQL details")
        elif self.engine == "sqlserver":
            if (not self.host or not self.user or not
                    self.password or not self.db):
                raise Exception("Missing SQL Server details")


def get_database(dbc):
    db = rnc_db.DatabaseSupporter()
    logger.info(
        "Opening database: host={h}, port={p}, db={d}, user={u}".format(
            h=dbc.host,
            p=dbc.port,
            d=dbc.db,
            u=dbc.user,
        )
    )
    if dbc.engine == "mysql":
        db.connect_to_database_mysql(
            server=dbc.host,
            port=dbc.port,
            database=dbc.db,
            user=dbc.user,
            password=dbc.password,
            autocommit=False  # NB therefore need to commit
        )
    elif dbc.engine == "sqlserver":
        db.connect_to_database_odbc_sqlserver(
            database=dbc.db,
            user=dbc.user,
            password=dbc.password,
            server=dbc.host,
            autocommit=False
        )
    return db


def ensure_valid_field_name(f):
    if not is_valid_field_name(f):
        raise Exception("Field name invalid: {}".format(f))


def ensure_valid_table_name(f):
    if not is_valid_table_name(f):
        raise Exception("Table name invalid: {}".format(f))


# =============================================================================
# Logger manipulation
# =============================================================================

def reset_logformat(logger, name="", debug=False):
    # logging.basicConfig() won't reset the formatter if another module
    # has called it, so always set the formatter like this.
    if name:
        namebit = name + ":"
    else:
        namebit = ""
    fmt = "%(levelname)s:%(name)s:" + namebit + "%(message)s"
    rnc_log.reset_logformat(logger, fmt=fmt)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

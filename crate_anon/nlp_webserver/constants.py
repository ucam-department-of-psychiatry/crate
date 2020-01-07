#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/constants.py

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

Constants for CRATE's implementation of an NLPRP server.

"""

KEY_PROCTYPE = "proctype"
PROCTYPE_GATE = "GATE"

# GATE_BASE_URL = "https://api.nhsta.gate.ac.uk/process-document"
GATE_BASE_URL = "https://nhsta-api.slam-services.gate.ac.uk/process-document"
NLP_WEBSERVER_CONFIG_ENVVAR = "CRATE_NLP_WEB_CONFIG"
SERVER_NAME = 'test_server'
SERVER_VERSION = '0.1'


class NlpServerConfigKeys(object):
    BACKEND_URL = "backend_url"
    BROKER_URL = "broker_url"
    ENCRYPTION_KEY = "encryption_key"
    USERS_FILE = "users_file"
    NLP_WEBSERVER_SECRET = "nlp_webserver.secret"
    PROCESSORS_PATH = "processors_path"
    SQLALCHEMY_PREFIX = "sqlalchemy."
    SQLALCHEMY_URL = SQLALCHEMY_PREFIX + "url"
    SQLALCHEMY_ECHO = SQLALCHEMY_PREFIX + "echo"
    REDIS_PASSWORD = "redis_password"
    REDIS_HOST = "redis_host"
    REDIS_PORT = "redis_port"
    REDIS_DB_NUMBER = "redis_db_number"


SQLALCHEMY_COMMON_OPTIONS = {
    # https://docs.sqlalchemy.org/en/13/core/engines.html
    'pool_recycle': 25200,  # in seconds; is 7 hours
    'pool_pre_ping': True,
}

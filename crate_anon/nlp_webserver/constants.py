r"""
crate_anon/nlp_webserver/constants.py

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

Constants for CRATE's implementation of an NLPRP server.

"""

KEY_PROCTYPE = "proctype"
PROCTYPE_GATE = "GATE"

# GATE_BASE_URL = "https://api.nhsta.gate.ac.uk/process-document"
GATE_BASE_URL = "https://nhsta-api.slam-services.gate.ac.uk/process-document"
NLP_WEBSERVER_CONFIG_ENVVAR = "CRATE_NLP_WEB_CONFIG"
NLP_WEBSERVER_CELERY_APP_NAME = "crate_anon.nlp_webserver.tasks"
SERVER_NAME = "test_server"
SERVER_VERSION = "0.1"


class NlpServerConfigKeys:
    SQLALCHEMY_PREFIX = "sqlalchemy."  # not itself a key

    BACKEND_URL = "backend_url"
    BROKER_URL = "broker_url"
    ENCRYPTION_KEY = "encryption_key"
    NLP_WEBSERVER_SECRET = "nlp_webserver.secret"
    PROCESSORS_PATH = "processors_path"
    REDIS_DB_NUMBER = "redis_db_number"
    REDIS_HOST = "redis_host"
    REDIS_PASSWORD = "redis_password"
    REDIS_PORT = "redis_port"
    SQLALCHEMY_ECHO = SQLALCHEMY_PREFIX + "echo"
    SQLALCHEMY_URL = SQLALCHEMY_PREFIX + "url"
    USERS_FILE = "users_file"


SQLALCHEMY_COMMON_OPTIONS = {
    # https://docs.sqlalchemy.org/en/13/core/engines.html
    "pool_recycle": 25200,  # in seconds; is 7 hours
    "pool_pre_ping": True,
}

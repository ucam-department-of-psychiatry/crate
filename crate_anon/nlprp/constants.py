#!/usr/bin/env python

r"""
crate_anon/nlprp/constants.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

Natural Language Processing Request Protocol (NLPRP) constants.

"""

from typing import Dict, List, Union

from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName


# =============================================================================
# Type definitions; see https://www.json.org/
# =============================================================================

# Types for the Python representation of JSON:
JsonLiteralType = Union[str, int, float, bool, None]
JsonValueType = Union[JsonLiteralType, Dict, List]
JsonObjectType = Dict[str, JsonValueType]
JsonArrayType = List[JsonValueType]

# Type for the string representation of JSON:
JsonAsStringType = str


# =============================================================================
# HTTP status codes
# =============================================================================

class HttpStatus(object):
    """
    HTTP status codes used by the NLPRP (plus a couple of others).
    """
    # 1xx: informational
    PROCESSING = 102

    # 2xx: success
    OK = 200
    ACCEPTED = 202
    NO_CONTENT = 204  # this HTTP status not emitted by an NLPRP server

    # 3xx: redirection
    # ... not used

    # 4xx: client error
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    NOT_FOUND = 404

    # 5xx: server error
    BAD_GATEWAY = 502
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503

    @classmethod
    def is_good_answer(cls, status: int) -> bool:
        """
        Is the given HTTP status code a satisfactory answer?
        """
        return 200 <= status <= 299 or status == cls.PROCESSING


# =============================================================================
# NLPRP strings
# =============================================================================

class NlprpKeys(object):
    """
    JSON dictionary keys used by the NLPRP.
    """
    ARGS = "args"  # request
    CLIENT_JOB_ID = "client_job_id"  # bidirectional
    CLIENT_JOB_IDS = "client_job_ids"  # request
    CODE = "code"  # response
    COLUMN_COMMENT = "column_comment"  # response
    COLUMN_NAME = "column_name"  # response
    COLUMN_TYPE = "column_type"  # response
    COLUMNS = "columns"  # response
    COMMAND = "command"  # request
    CONTENT = "content"  # request
    DATA_TYPE = "data_type"  # response
    DATETIME_COMPLETED = "datetime_completed"  # response
    DATETIME_SUBMITTED = "datetime_submitted"  # response
    DELETE_ALL = "delete_all"  # request
    DESCRIPTION = "description"  # response
    ERRORS = "errors"  # response
    INCLUDE_TEXT = "include_text"  # request
    IS_DEFAULT_VERSION = "is_default_version"  # response
    IS_NULLABLE = "is_nullable"  # response
    MESSAGE = "message"  # response
    METADATA = "metadata"  # bidirectional
    NAME = "name"  # bidirectional
    PROCESSORS = "processors"  # bidirectional
    PROTOCOL = "protocol"  # bidirectional
    QUEUE = "queue"  # bidirectional
    QUEUE_ID = "queue_id"  # response
    QUEUE_IDS = "queue_ids"  # request
    RESULTS = "results"  # response
    SCHEMA_TYPE = "schema_type"  # response
    SERVER_INFO = "server_info"  # response
    SQL_DIALECT = "sql_dialect"  # response
    STATUS = "status"  # response
    SUCCESS = "success"  # response
    TABULAR_SCHEMA = "tabular_schema"  # response
    TEXT = "text"  # request
    TITLE = "title"  # response
    VERSION = "version"  # bidirectional


class NlprpValues(object):
    """
    JSON dictionary values used by the NLPRP.
    """
    BUSY = "busy"
    NLPRP_PROTOCOL_NAME = "nlprp"
    READY = "ready"
    TABULAR = "tabular"  # for schema_type
    UNKNOWN = "unknown"  # for schema_type


class NlprpCommands(object):
    """
    NLPRP commands.
    """
    LIST_PROCESSORS = "list_processors"
    PROCESS = "process"
    SHOW_QUEUE = "show_queue"
    FETCH_FROM_QUEUE = "fetch_from_queue"
    DELETE_FROM_QUEUE = "delete_from_queue"


ALL_NLPRP_COMMANDS = [v for k, v in NlprpCommands.__dict__.items()
                      if not k.startswith("_")]


class SqlDialects(object):
    """
    SQL dialects supported by the NLPRP.
    """
    MSSQL = SqlaDialectName.MSSQL
    MYSQL = SqlaDialectName.MYSQL
    ORACLE = SqlaDialectName.ORACLE
    POSTGRES = SqlaDialectName.POSTGRES
    SQLITE = SqlaDialectName.SQLITE


ALL_SQL_DIALECTS = [v for k, v in SqlDialects.__dict__.items()
                    if not k.startswith("_")]

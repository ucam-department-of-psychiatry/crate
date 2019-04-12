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


class HttpStatus(object):
    """
    HTTP status codes used by the NLPRP.
    """
    # 1xx: informational
    PROCESSING = 102
    # 2xx: success
    OK = 200
    ACCEPTED = 202
    NO_CONTENT = 204
    # 3xx: redirection
    # ... not used
    # 4xx: client error
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    # 5xx: server error
    SERVICE_UNAVAILABLE = 503


class NlprpKeys(object):
    """
    JSON dictionary keys used by the NLPRP.
    """
    ARGS = "args"  # request
    CLIENT_JOB_ID = "client_job_id"  # bidirectional
    CLIENT_JOB_IDS = "client_job_ids"  # request
    CODE = "code"  # response
    COMMAND = "command"  # request
    CONTENT = "content"  # request
    DATETIME_COMPLETED = "datetime_completed"  # response
    DATETIME_SUBMITTED = "datetime_submitted"  # response
    DELETE_ALL = "delete_all"  # request
    DESCRIPTION = "description"  # response
    ERRORS = "errors"  # response
    INCLUDE_TEXT = "include_text"  # request
    IS_DEFAULT_VERSION = "is_default_version"  # response
    MESSAGE = "message"  # response
    METADATA = "metadata"  # bidirectional
    NAME = "name"  # bidirectional
    PROCESSORS = "processors"  # bidirectional
    PROTOCOL = "protocol"  # bidirectional
    QUEUE = "queue"  # bidirectional
    QUEUE_ID = "queue_id"  # response
    QUEUE_IDS = "queue_ids"  # request
    RESULTS = "results"  # response
    SERVER_INFO = "server_info"  # response
    STATUS = "status"  # response
    SUCCESS = "success"  # response
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

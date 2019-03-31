#!/usr/bin/env python

r"""
crate_anon/nlprp/api.py

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

Validate Natural Language Processing Request Protocol (NLPRP) objects.

"""

import json
import gzip
from typing import Any, Dict, Union

from semantic_version import Version

from crate_anon.nlprp.constants import (
    NlprpKeys,
    NlprpValues,
    ALL_NLPRP_COMMANDS,
)
from crate_anon.nlprp.version import NLPRP_VERSION_STRING


# =============================================================================
# Constants
# =============================================================================

DEFAULT_SERVER_NAME = "CRATE NLPRP server"
DEFAULT_PROTOCOL_INFO = {
    NlprpKeys.NAME: NlprpValues.NLPRP_PROTOCOL_NAME,
    NlprpKeys.VERSION: NLPRP_VERSION_STRING,
}
DEFAULT_SERVER_INFO = {
    NlprpKeys.NAME: DEFAULT_SERVER_NAME,
    NlprpKeys.VERSION: NLPRP_VERSION_STRING,
}


# =============================================================================
# Validity checkers
# =============================================================================

def is_nlprp_protocol_valid(x: Dict[str, Any],
                            min_version: Version = None,
                            max_version: Version = None) -> bool:
    """
    Is the parameter a valid NLPRP request/response object?

    Args:
        x: dictionary to test
        min_version: minimum NLPRP version to accept; None for no minimum
        max_version: maximum NLPRP version to accept; None for no maximum
    """
    try:
        protocol = x.get(NlprpKeys.PROTOCOL, None)  # type: Dict[str, Any]
        # ... will raise AttributeError if not a dict
        protocol_name = protocol[NlprpKeys.NAME]
        assert protocol_name.lower() == NlprpValues.NLPRP_PROTOCOL_NAME
        protocol_version = Version(protocol[NlprpKeys.VERSION])
        # ... the Version() call may raise TypeError, ValueError
        if min_version is not None:
            assert protocol_version >= min_version
        if max_version is not None:
            assert protocol_version <= max_version
    except (AssertionError, AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


def is_valid_nlprp_request(x: Dict[str, Any],
                           min_version: Version = None,
                           max_version: Version = None) -> bool:
    """
    Is the parameter a valid NLPRP request (client to server)?

    Args:
        x: dictionary to test
        min_version: minimum NLPRP version to accept; None for no minimum
        max_version: maximum NLPRP version to accept; None for no maximum
    """
    try:
        assert is_nlprp_protocol_valid(
            x, min_version=min_version, max_version=max_version)
        command = x[NlprpKeys.COMMAND].lower()  # case-insensitive
        assert command in ALL_NLPRP_COMMANDS
    except (AssertionError, AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


def is_valid_nlprp_response(x: Dict[str, Any],
                            min_version: Version = None,
                            max_version: Version = None) -> bool:
    """
    Is the parameter a valid NLPRP response (server to client)?

    Args:
        x: dictionary to test
        min_version: minimum NLPRP version to accept; None for no minimum
        max_version: maximum NLPRP version to accept; None for no maximum
    """
    try:
        assert is_nlprp_protocol_valid(
            x, min_version=min_version, max_version=max_version)
        # *** more here?
    except (AssertionError, AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


# =============================================================================
# Dictionary creators
# =============================================================================

def make_nlprp_dict() -> Dict[str, Any]:
    """
    Creates the basic dictionary used by the NLPRP protocol.
    """
    return {
        NlprpKeys.PROTOCOL: DEFAULT_PROTOCOL_INFO
    }


def make_nlprp_request(command: str,
                       command_args: Any = None) -> Dict[str, Any]:
    """
    Creates a NLPRP request (client to server) dictionary.

    Args:
        command: NLPRP command
        command_args: optional argument dictionary
    """
    assert command in ALL_NLPRP_COMMANDS
    d = make_nlprp_dict()
    d[NlprpKeys.COMMAND] = command
    if command_args:
        d[NlprpKeys.ARGS] = command_args
    return d


def make_nlprp_response(http_status: int,
                        reply_args: Dict[str, Any] = None,
                        server_info: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Creates a NLPRP response (server to client) dictionary.

    Args:
        http_status: HTTP status code
        reply_args: reply dictionary
        server_info: ``server_info`` dictionary, or ``None`` for a default
    """
    assert http_status is not None
    server_info = server_info or DEFAULT_SERVER_INFO
    reply_args = reply_args or {}  # type: Dict[str, Any]
    d = make_nlprp_dict()
    d[NlprpKeys.STATUS] = http_status
    d[NlprpKeys.SERVER_INFO] = server_info
    d.update(**reply_args)
    return d


# =============================================================================
# Generic object
# =============================================================================

class NlprpMessage(object):
    """
    Represents an NLPRP (natural language processing request protocol) message,
    be it a request (client to server) or a response (server to client).
    """

    def __init__(self,
                 data: Union[str, bytes, Dict[str, Any]],
                 data_is_gzipped: bool = False) -> None:
        """
        Initialize with data as either

        - gzipped bytes, representing bytes...
        - bytes, representing a UTF-8 encoded str...
        - str, representing a JSON-encoded dict...
        - a dict.

        Args:
            data: the data
            data_is_gzipped: if ``data`` is of type ``bytes``, is it gzipped?
        """
        self._data = {}  # type: Dict[str, Any]
        if isinstance(data, bytes):
            if data_is_gzipped:
                data = gzip.decompress(data)
            data = data.decode("utf-8")  # now it's a str
        if isinstance(data, str):
            data = json.loads(data)  # type: Dict[str, Any]
        if isinstance(data, dict):
            self._data = data

    def __str__(self) -> str:
        return repr(self._data)

    @property
    def dict(self) -> Dict[str, Any]:
        """
        Returns the underlying dictionary.
        """
        return self._data

    @property
    def data_str(self) -> str:
        """
        Returns a JSON-encoded version of the underlying dictionary.
        """
        return json.dumps(self._data)

    @property
    def data_bytes(self) -> bytes:
        """
        Returns a UTF-8 encoded version of the JSON-encoded underlying
        dictionary.
        """
        return self.data_str.encode("utf-8")

    @property
    def data_gzipped(self) -> bytes:
        """
        Returns a GZIP-compressed version of ``data_bytes``.
        """
        return gzip.compress(self.data_bytes)

    def protocol_valid(self,
                       min_version: Version = None,
                       max_version: Version = None) -> bool:
        """
        Is the protocol valid?

        Args:
            min_version: minimum NLPRP version to accept; None for no minimum
            max_version: maximum NLPRP version to accept; None for no maximum
        """
        return is_nlprp_protocol_valid(self._data,
                                       min_version=min_version,
                                       max_version=max_version)

    def valid(self,
              min_version: Version = None,
              max_version: Version = None) -> bool:
        """
        Is the message valid?

        Overridden in subclasses to perform more specific checks.

        Args:
            min_version: minimum NLPRP version to accept; None for no minimum
            max_version: maximum NLPRP version to accept; None for no maximum
        """
        return self.protocol_valid(min_version=min_version,
                                   max_version=max_version)


class NlprpRequest(NlprpMessage):
    """
    Represents an NLPRP request (client to server).
    """

    def __init__(self,
                 command: str = None,
                 command_args: Dict[str, Any] = None,
                 data: Union[str, bytes, Dict[str, Any]] = None,
                 data_is_gzipped: bool = False) -> None:
        """
        Initialize with one of the following sets of parameters:

        - ``command`` and optionally ``args`` -- typically used by clients
          creating a request to send to the server
        - ``data`` -- typically used by servers parsing a client's request

        Args:
            command: NLPRP command
            command_args: optional argument dictionary
            data: data as gzipped bytes, bytes, str, or a dict
            data_is_gzipped: if ``data`` is used, and is of type ``bytes``,
                is it GZIP-compressed?
        """
        super().__init__(data=data, data_is_gzipped=data_is_gzipped)
        if not data:
            # Build an NLPRP message from command/args
            assert command, "data not specified, so must specify command"
            self._data = make_nlprp_request(command, command_args)

    def valid(self,
              min_version: Version = None,
              max_version: Version = None) -> bool:
        """
        Is the request valid?

        Args:
            min_version: minimum NLPRP version to accept; None for no minimum
            max_version: maximum NLPRP version to accept; None for no maximum
        """
        return is_valid_nlprp_request(self._data,
                                      min_version=min_version,
                                      max_version=max_version)

    @property
    def command(self) -> str:
        """
        Returns the NLPRP command.
        """
        return self._data.get(NlprpKeys.COMMAND, "")

    @property
    def args(self) -> Dict[str, Any]:
        """
        Returns the NLPRP command arguments.
        """
        return self._data.get(NlprpKeys.ARGS, {})


class NlprpResponse(NlprpMessage):
    """
    Represents an NLPRP response (server to client).
    """

    def __init__(self,
                 data: Union[str, bytes, Dict[str, Any]] = None,
                 data_is_gzipped: bool = False,
                 http_status: int = 200,
                 reply_args: Dict[str, Any] = None,
                 server_info: Dict[str, Any] = None) -> None:
        """
        Initialize with one of the following sets of parameters:

        - ``data`` -- typically used by clients parsing a server's reply
        - ``http_status`` and ``reply_args`` -- typically used by servers
          creating a reply to send to the client

        Args:
            data: data as gzipped bytes, bytes, str, or a dict
            data_is_gzipped: if ``data`` is used, and is of type ``bytes``,
                is it GZIP-compressed?
            http_status: HTTP status code
            reply_args: any other parts to the reply
        """
        super().__init__(data=data, data_is_gzipped=data_is_gzipped)
        if not data:
            # Build a reply
            self._data = make_nlprp_response(
                http_status=http_status,
                reply_args=reply_args,
                server_info=server_info,
            )

    @property
    def status(self) -> int:
        """
        Returns the status of the NLPRP response, or -1 if it's missing.
        """
        return self._data.get(NlprpKeys.STATUS, -1)

    @property
    def server_info(self) -> Dict[str, Any]:
        """
        Returns the ``server_info`` part of the NLPRP response.
        """
        return self._data.get(NlprpKeys.SERVER_INFO, {})

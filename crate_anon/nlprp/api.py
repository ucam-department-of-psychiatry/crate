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

import datetime
import json
import gzip
from typing import Any, Dict, List, Optional, Union

from cardinal_pythonlib.datetimefunc import (
    coerce_to_pendulum,
    convert_datetime_to_utc,
    get_now_localtz_pendulum,
    get_now_utc_pendulum,
    pendulum_to_datetime,
    pendulum_to_utc_datetime_without_tz,
)
from cardinal_pythonlib.reprfunc import auto_repr
import pendulum
from pendulum import DateTime as Pendulum  # NB name clash with SQLAlchemy
from semantic_version import Version

from crate_anon.common.constants import JSON_SEPARATORS_COMPACT
from crate_anon.nlprp.constants import (
    HttpStatus,
    JsonArrayType,
    JsonAsStringType,
    JsonObjectType,
    JsonValueType,
    NlprpKeys,
    NlprpValues,
    ALL_NLPRP_COMMANDS,
)
from crate_anon.nlprp.errors import (
    BAD_REQUEST,
    key_missing_error,
    mkerror,
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
# Date/time conversion to/from NLPRP format
# =============================================================================

def nlprp_datetime_to_pendulum(ndt: str) -> Pendulum:
    """
    The NLPRP date/time format is ISO-8601 with all three of: date, time,
    timezone.

    Example:

    .. code-block:: none

        "2019-08-09T17:26:20.123456+01:00"

    Args:
        ndt: date/time in ISO-8601 format with timezone

    Returns:
        :class:`pendulum.DateTime` (with timezone information)
    """
    return pendulum.parse(ndt)


def nlprp_datetime_to_datetime_with_tz(ndt: str) -> datetime.datetime:
    """
    Converts a NLPRP date/time (see :func:`nlprp_iso_datetime_to_pendulum`) to
    a :class:`datetime.datetime` with timezone information.

    Args:
        ndt: date/time in ISO-8601 format with timezone

    Returns:
        datetime.datetime: with timezone information
    """
    p = nlprp_datetime_to_pendulum(ndt)
    return pendulum_to_datetime(p)


def nlprp_datetime_to_datetime_utc_no_tzinfo(ndt: str) -> \
        datetime.datetime:
    """
    Converts a NLPRP date/time (see :func:`nlprp_iso_datetime_to_pendulum`) to
    a :class:`datetime.datetime` in UTC with no timezone information.

    Args:
        ndt: date/time in ISO-8601 format with timezone

    Returns:
        datetime.datetime: in UTC with no timezone information
    """
    p = nlprp_datetime_to_pendulum(ndt)
    return pendulum_to_utc_datetime_without_tz(p)


def pendulum_to_nlprp_datetime(p: Pendulum, to_utc: bool = True) -> str:
    """
    Converts a :class:`pendulum.Pendulum` to the ISO string format (with
    timezone) used by the NLPRP.
    """
    if to_utc:
        p = convert_datetime_to_utc(p)
    return p.isoformat()


def datetime_to_nlprp_datetime(dt: datetime.datetime,
                               assume_utc: bool = True) -> str:
    """
    Converts a :class:`datetime.datetime` to the ISO string format (with
    timezone) used by the NLPRP.

    If the datetime.datetime object has no timezone info, then assume the local
    timezone if ``assume_local`` is true; otherwise, assume UTC.
    """
    p = coerce_to_pendulum(dt, assume_local=not assume_utc)
    return pendulum_to_nlprp_datetime(p)


def nlprp_datetime_now(as_local: bool = True) -> str:
    """
    Returns the time now, as a string suitable for use with NLPRP.

    Args:
        as_local: use local timezone? (Otherwise, use UTC.)
    """
    now = get_now_localtz_pendulum() if as_local else get_now_utc_pendulum()
    return pendulum_to_nlprp_datetime(now)


# =============================================================================
# Get arguments from JSON objects
# =============================================================================

def json_get_bool(x: JsonObjectType, key: str, default: bool = None,
                  required: bool = False) -> bool:
    """
    Gets a boolean parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        default: the default value
        required: is it mandatory, or can it be missing or ``null``?

    Returns:
        bool: the result, or the default

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return default
    if not isinstance(value, bool):
        mkerror(BAD_REQUEST, f"{key!r} parameter not Boolean")
    return value


def json_get_int(x: JsonObjectType, key: str, default: int = None,
                 required: bool = False) -> int:
    """
    Gets an integer parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        default: the default value
        required: is it mandatory, or can it be missing or ``null``?

    Returns:
        int: the result, or the default

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key, default)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return default
    if not isinstance(value, int):
        mkerror(BAD_REQUEST, f"{key!r} parameter not integer")
    return value


def json_get_float(x: JsonObjectType, key: str, default: int = None,
                   required: bool = False) -> int:
    """
    Gets a float (or int) parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        default: the default value
        required: is it mandatory, or can it be missing or ``null``?

    Returns:
        float: the result, or the default

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key, default)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return default
    if not isinstance(value, (float, int)):
        mkerror(BAD_REQUEST, f"{key!r} parameter not float")
    return value


def json_get_str(x: JsonObjectType, key: str, default: str = None,
                 required: bool = False) -> str:
    """
    Gets a string parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        default: the default value
        required: is it mandatory, or can it be missing or ``null``?

    Returns:
        str: the result, or the default

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key, default)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return default
    if not isinstance(value, str):
        mkerror(BAD_REQUEST, f"{key!r} parameter not string")
    return value


def json_get_array(x: JsonObjectType, key: str,
                   required: bool = False) -> JsonArrayType:
    """
    Gets a array (list) parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        required: is the array required?

    Returns:
        list: the result, or ``[]`` if the parameter is missing and
        ``required == False``.

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return []  # type: JsonArrayType
    if not isinstance(value, list):
        mkerror(BAD_REQUEST, f"{key!r} parameter not a JSON array (list)")
    return value


def json_get_array_of_str(x: JsonObjectType, key: str,
                          required: bool = False) -> List[str]:
    """
    Gets an array of strings from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        required: is the array required?

    Returns:
        list: the result, or ``[]`` if the parameter is missing and
        ``required == False``.

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return []  # type: JsonArrayType
    if not isinstance(value, list):
        mkerror(BAD_REQUEST, f"{key!r} parameter not a JSON array (list)")
    if not all(isinstance(x, str) for x in value):
        mkerror(BAD_REQUEST, f"Non-string value as part of {key!r}")
    return value


def json_get_object(x: JsonObjectType, key: str,
                    required: bool = False) -> JsonObjectType:
    """
    Gets an object (dictionary) parameter from part of the JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        required: is the object required?

    Returns:
        list: the result, or ``{}`` if the parameter is missing and
        ``required == False``.

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return {}  # type: JsonArrayType
    if not isinstance(value, dict):
        mkerror(BAD_REQUEST,
                f"{key!r} parameter not a JSON object (dictionary)")
    return value


def json_get_value(x: JsonValueType, key: str, default: JsonValueType = None,
                   required: bool = False) -> JsonValueType:
    """
    Gets an JSON value (object, array, or literal) parameter from part of the
    JSON request.

    Args:
        x: a JSON object (dictionary)
        key: the name of the key
        default: the default value
        required: is the value required?

    Returns:
        the result, or the default

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = x.get(key)
    if value is None:  # missing, or "null"
        if required:
            raise key_missing_error(key)
        else:
            return default
    if not isinstance(value, (dict, list, str, int, float, bool)):
        # None is covered above
        mkerror(BAD_REQUEST,
                f"{key!r} parameter not a JSON value")
    return value


def json_get_toplevel_args(nlprp_request: JsonObjectType,
                           required: bool = True) -> JsonObjectType:
    """
    Returns the top-level arguments for a NLPRP request.

    Args:
        nlprp_request: the NLPRP request object
        required: are the args required?

    Returns:
        dict: the result

    Raises:
        :exc:`NlprpError` if the value is bad, or is missing and required.
    """
    value = nlprp_request.get(NlprpKeys.ARGS)
    if value is None:
        if required:
            raise key_missing_error(NlprpKeys.ARGS, is_args=True)
        else:
            return {}  # type: JsonArrayType
    if not isinstance(value, dict):
        mkerror(BAD_REQUEST,
                f"{NlprpKeys.ARGS!r} parameter not a JSON object (dictionary)")
    return value


# =============================================================================
# Validity checkers
# =============================================================================

def is_nlprp_protocol_valid(x: JsonObjectType,
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
        protocol = x.get(NlprpKeys.PROTOCOL, None)  # type: JsonObjectType
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


def is_valid_nlprp_request(x: JsonObjectType,
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


def is_valid_nlprp_response(x: JsonObjectType,
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
    except (AssertionError, AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


# =============================================================================
# Dictionary creators
# =============================================================================

def make_nlprp_dict() -> JsonObjectType:
    """
    Creates the basic dictionary used by the NLPRP protocol.
    """
    return {
        NlprpKeys.PROTOCOL: DEFAULT_PROTOCOL_INFO
    }


def make_nlprp_request(command: str,
                       command_args: Any = None) -> JsonObjectType:
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
                        reply_args: JsonObjectType = None,
                        server_info: JsonObjectType = None) -> JsonObjectType:
    """
    Creates a NLPRP response (server to client) dictionary.

    Args:
        http_status: HTTP status code
        reply_args: reply dictionary
        server_info: ``server_info`` dictionary, or ``None`` for a default
    """
    assert http_status is not None
    server_info = server_info or DEFAULT_SERVER_INFO
    reply_args = reply_args or {}  # type: JsonObjectType
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
                 data: Union[str, bytes, JsonObjectType],
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
        self._data = {}  # type: JsonObjectType
        if isinstance(data, bytes):
            if data_is_gzipped:
                data = gzip.decompress(data)
            # noinspection PyTypeChecker
            data = data.decode("utf-8")  # now it's a str
        if isinstance(data, str):
            data = json.loads(data)  # type: JsonObjectType
        if isinstance(data, dict):
            self._data = data

    def __str__(self) -> str:
        return repr(self._data)

    @property
    def dict(self) -> JsonObjectType:
        """
        Returns the underlying dictionary.
        """
        return self._data

    @property
    def data_str(self) -> JsonAsStringType:
        """
        Returns a JSON-encoded version of the underlying dictionary.
        """
        return json.dumps(self._data, separators=JSON_SEPARATORS_COMPACT)

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
                 command_args: JsonObjectType = None,
                 data: Union[str, bytes, JsonObjectType] = None,
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
        return json_get_str(self._data, NlprpKeys.COMMAND, "")

    @property
    def args(self) -> JsonObjectType:
        """
        Returns the NLPRP command arguments.
        """
        return json_get_object(self._data, NlprpKeys.ARGS, required=False)


class NlprpResponse(NlprpMessage):
    """
    Represents an NLPRP response (server to client).
    """

    def __init__(self,
                 data: Union[str, bytes, JsonObjectType] = None,
                 data_is_gzipped: bool = False,
                 http_status: int = HttpStatus.OK,
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
        return json_get_int(self._data, NlprpKeys.STATUS, -1)

    @property
    def server_info(self) -> JsonObjectType:
        """
        Returns the ``server_info`` part of the NLPRP response.
        """
        return json_get_object(self._data, NlprpKeys.SERVER_INFO,
                               required=False)


class NlprpServerProcessor(object):
    """
    Class for containing information about am NLP processor known to an NLPRP
    server.
    """

    def __init__(self,
                 name: str,
                 title: str,
                 version: str,
                 is_default_version: bool,
                 description: str,
                 schema_type: str = NlprpValues.UNKNOWN,
                 sql_dialect: Optional[str] = None,
                 tabular_schema: Optional[Dict[str, Any]] = None) -> None:
        assert schema_type in (NlprpValues.UNKNOWN, NlprpValues.TABULAR), (
            "'schema_type' must be one of '{NlprpValues.UNKNOWN}', "
            "'{NlprpValues.TABULAR}' for each processor.")
        self.name = name
        self.title = title
        self.version = version
        self.is_default_version = is_default_version
        self.description = description
        self.schema_type = schema_type
        self.sql_dialect = sql_dialect
        self.tabular_schema = tabular_schema

    @property
    def infodict(self) -> Dict[str, Any]:
        d = {
            NlprpKeys.NAME: self.name,
            NlprpKeys.TITLE: self.title,
            NlprpKeys.VERSION: self.version,
            NlprpKeys.IS_DEFAULT_VERSION: self.is_default_version,
            NlprpKeys.DESCRIPTION: self.description,
            NlprpKeys.SCHEMA_TYPE: self.schema_type,
        }
        if self.schema_type == NlprpValues.TABULAR:
            d[NlprpKeys.SQL_DIALECT] = self.sql_dialect
            d[NlprpKeys.TABULAR_SCHEMA] = self.tabular_schema
        return d

    def __str__(self) -> str:
        return str(self.infodict)

    def __repr__(self) -> str:
        return auto_repr(self)

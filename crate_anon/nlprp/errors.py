#!/usr/bin/env python

r"""
crate_anon/nlprp/errors.py

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

Errors used by NLPRP servers.

"""

from cardinal_pythonlib.reprfunc import auto_repr
from crate_anon.nlprp.constants import HttpStatus


# =============================================================================
# NlprpError
# =============================================================================

class NlprpError(Exception):
    """
    Represents an HTTP (and NLPRP) error. Is also an Exception, so can
    be raised.
    """
    def __init__(self,
                 http_status: int,
                 code: int,
                 message: str,
                 description: str = "") -> None:
        self.http_status = http_status
        self.code = code
        self.message = message
        self.description = description

    def __str__(self) -> str:
        return (
            f"NLPRP error: HTTP status {self.http_status}, "
            f"code {self.code}; "
            f"message {self.message!r}; "
            f"description {self.description!r}"
        )

    def __repr__(self) -> str:
        return auto_repr(self)


# =============================================================================
# Common base errors
# =============================================================================

BAD_REQUEST = NlprpError(
    HttpStatus.BAD_REQUEST, HttpStatus.BAD_REQUEST,
    "Bad request", "Request was malformed"
)
UNAUTHORIZED = NlprpError(
    HttpStatus.UNAUTHORIZED, HttpStatus.UNAUTHORIZED,
    "Unauthorized",
    "The username/password combination given is incorrect"
)
NOT_FOUND = NlprpError(
    HttpStatus.NOT_FOUND, HttpStatus.NOT_FOUND,
    "Not Found",
    "The information requested was not found"
)
INTERNAL_SERVER_ERROR = NlprpError(
    HttpStatus.INTERNAL_SERVER_ERROR, HttpStatus.INTERNAL_SERVER_ERROR,
    "Internal Server Error",
    "An internal server error has occured"
)


# =============================================================================
# Helper functions
# =============================================================================

def mkerror(base_error: NlprpError, description: str = None) -> NlprpError:
    """
    Makes a derived error by copying an existing one and amending its
    description.
    """
    return NlprpError(
        http_status=base_error.http_status,
        code=base_error.code,
        message=base_error.message,
        description=description or base_error.description
    )


def key_missing_error(key: str = "",
                      is_args: bool = False) -> NlprpError:
    """
    Returns a '400: Bad Request' error response stating that a key is
    missing from 'args' in the request, or the key 'args' itself is missing
    """
    if is_args:
        description = "Request did not contain top-level key 'args'"
    else:
        description = f"Args did not contain key '{key}'"
    return mkerror(BAD_REQUEST, description)


def no_such_proc_error(name: str,
                       version: str = None) -> NlprpError:
    """
    "No such processor" error.

    Args:
        name: requested processor name
        version: requested processor version
    """
    return mkerror(
        BAD_REQUEST,
        f"Processor {name!r}, version {version!r} does not exist")

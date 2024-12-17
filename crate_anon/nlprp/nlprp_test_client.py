#!/usr/bin/env python

r"""
crate_anon/nlprp/nlprp_test_client.py

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

crate_anon/docs/sources/nlp/nlprp_test_client.py
Simple test client for the NLPRP interface.

"""

import argparse
import logging
import requests
from typing import Any, NoReturn

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from requests.auth import HTTPBasicAuth

from crate_anon.version import require_minimum_python_version
from crate_anon.nlprp.api import NlprpRequest, NlprpResponse
from crate_anon.nlprp.constants import NlprpCommands

require_minimum_python_version()

log = logging.getLogger(__name__)


def get_response(
    url: str,
    command: str,
    command_args: Any = None,
    transmit_compressed: bool = False,
    receive_compressed: bool = True,
    username: str = "",
    password: str = "",
) -> NlprpResponse:
    """
    Illustrate sending to/receiving from an NLPRP server, using HTTP basic
    authentication.

    Args:
        url: URL to send request to
        command: NLPRP command
        command_args: arguments to be sent with the NLPRP command;
            ``json.dumps()`` is applied to this object first
        transmit_compressed: compress requests via GZIP encoding
        receive_compressed: tell the server we will accept responses compresed
            via GZIP encoding
        username: username for basic HTTP authentication
        password: password for basic HTTP authentication
    """

    # -------------------------------------------------------------------------
    # How we fail
    # -------------------------------------------------------------------------
    def fail(msg: str) -> NoReturn:
        log.warning(msg)
        raise ValueError(msg)

    # -------------------------------------------------------------------------
    # Build request and send it
    # -------------------------------------------------------------------------
    req = NlprpRequest(command=command, command_args=command_args)
    log.info(f"Sending request: {req}")
    headers = {"Content-Type": "application/json"}
    if transmit_compressed:
        headers["Content-Encoding"] = "gzip"
        request_data = req.data_gzipped
    else:
        request_data = req.data_bytes
    if receive_compressed:
        headers["Accept-Encoding"] = "gzip, deflate"
        # As it turns out, the "requests" library adds this anyway!
    log.debug(
        f"Sending to URL {url!r}: headers {headers!r}, "
        f"data {request_data!r}"
    )
    r = requests.post(
        url,
        data=request_data,
        headers=headers,
        auth=HTTPBasicAuth(username, password),
    )
    # -------------------------------------------------------------------------
    # Process response
    # -------------------------------------------------------------------------
    # - Note that the "requests" module automatically handles "gzip" and
    #   "deflate" transfer-encodings from the server; see
    #   http://docs.python-requests.org/en/master/user/quickstart/.
    # - The difference between gzip and deflate:
    #   https://stackoverflow.com/questions/388595/why-use-deflate-instead-of-gzip-for-text-files-served-by-apache  # noqa: E501
    log.debug(
        f"Reply has status_code={r.status_code}, headers={r.headers!r}, "
        f"text={r.text!r}"
    )
    try:
        response = NlprpResponse(data=r.text)
        # "r.text" automatically does gzip decode
    except (
        ValueError
    ):  # includes simplejson.errors.JSONDecodeError, json.decoder.JSONDecodeError  # noqa: E501
        fail("Reply was not JSON")
        response = None  # for type checker
    log.debug(f"Response JSON decoded to: {response.dict!r}")
    try:
        assert response.valid()
    except (AssertionError, AttributeError, KeyError):
        fail("Reply was not in the NLPRP protocol")
    return response


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--url", default="http://0.0.0.0:6543", help="URL of server"
    )
    parser.add_argument(
        "--transmit_compressed",
        action="store_true",
        help="Send data compressed",
    )
    parser.add_argument(
        "--receive_compressed",
        action="store_true",
        help="Accept compressed data from the server",
    )
    parser.add_argument(
        "--username",
        default="",
        help="Username for HTTP basic authentication on server",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Password for HTTP basic authentication on server",
    )
    cmdargs = parser.parse_args()
    response = get_response(
        url=cmdargs.url,
        command=NlprpCommands.LIST_PROCESSORS,
        transmit_compressed=cmdargs.transmit_compressed,
        receive_compressed=cmdargs.receive_compressed,
        username=cmdargs.username,
        password=cmdargs.password,
    )
    log.info(f"Received reply: {response.dict!r}")


if __name__ == "__main__":
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    main()

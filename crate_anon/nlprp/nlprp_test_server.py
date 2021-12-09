#!/usr/bin/env python

r"""
crate_anon/nlprp/nlprp_test_server.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Simple test server for the NLPRP interface.

"""

import argparse
import logging
from typing import Any, Dict
from wsgiref.simple_server import make_server

from cardinal_pythonlib.httpconst import HttpStatus
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from pyramid.config import Configurator
from pyramid.request import Request
from pyramid.response import Response
from semantic_version import Version

from crate_anon.version import require_minimum_python_version
from crate_anon.nlprp.constants import NlprpKeys
from crate_anon.nlprp.api import NlprpRequest, NlprpResponse

require_minimum_python_version()

log = logging.getLogger(__name__)

SERVER_NLPRP_VERSION = Version("0.1.0")


# noinspection PyUnusedLocal
def cmd_list_processors(hreq: Request, nreq: NlprpRequest) -> Dict[str, Any]:
    """
    Specimen (dummy) implementation of the "list_processors" command.
    """
    return {
        NlprpKeys.PROCESSORS: [
            {
                NlprpKeys.NAME: "my_first_processor",
                NlprpKeys.TITLE: "My First NLP Processor",
                NlprpKeys.VERSION: "0.0.1",
                NlprpKeys.IS_DEFAULT_VERSION: True,
                NlprpKeys.DESCRIPTION: "Finds mentions of the word Alice",
            },
            {
                NlprpKeys.NAME: "my_second_processor",
                NlprpKeys.TITLE: "My Second NLP Processor",
                NlprpKeys.VERSION: "0.0.2",
                NlprpKeys.IS_DEFAULT_VERSION: True,
                NlprpKeys.DESCRIPTION: "Finds mentions of the word Bob",
            },
        ]
    }


def nlprp_server(request: Request) -> Response:
    """
    Specimen NLPRP server for Pyramid.

    Args:
        request: the Pyramid :class:`Request` object

    Returns:
        a Pyramid :class:`Response`
    """
    headers = request.headers
    request_is_gzipped = headers.get("Content-Encoding", "") == "gzip"
    client_accepts_gzip = "gzip" in headers.get("Accept-Encoding", "")
    body = request.body
    log.debug(
        f"===========================================\n"
        f"Received request {request!r}:\n"
        f"    headers={dict(headers)!r}\n"
        f"    body={body!r}\n"
        f"    request_is_gzipped={request_is_gzipped}\n"
        f"    client_accepts_gzip={client_accepts_gzip}"
    )
    try:
        nreq = NlprpRequest(data=body, data_is_gzipped=request_is_gzipped)
        log.info(f"NLPRP request is {nreq}")
        assert nreq.valid()
        # Establish command
        log.debug(f"command={nreq.command!r}, args={nreq.args!r}")
    except Exception:
        # Could do more here!
        raise

    # Process NLPRP command
    http_status = HttpStatus.OK
    if nreq.command == "list_processors":
        replydict = cmd_list_processors(request, nreq)
    else:
        raise NotImplementedError()
    assert isinstance(replydict, dict), "Bug in server!"
    reply = NlprpResponse(http_status=http_status, reply_args=replydict)
    log.info(f"Sending NLPRP response: {reply}")

    # Create the HTTP response
    response = Response(reply.data_bytes, status=http_status)
    # Compress the response?
    if client_accepts_gzip:
        response.encode_content("gzip")
    # Done
    log.debug(f"Sending HTTP response: headers={response.headers}, "
              f"body={response.body}")
    return response


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Hostname to serve on"
    )
    parser.add_argument(
        "--port", default=6543,
        help="TCP port to serve on"
    )
    cmdargs = parser.parse_args()
    with Configurator() as config:
        config.add_route('only_route', '/')
        config.add_view(nlprp_server, route_name='only_route')
        app = config.make_wsgi_app()
    server = make_server(cmdargs.host, cmdargs.port, app)
    log.info(f"Starting server on {cmdargs.host}:{cmdargs.port}")
    server.serve_forever()


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    main()

#!/usr/bin/env python

"""
crate_anon/crateweb/core/management/commands/runcpserver.py

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

**Django management command framework for CherryPy.**

- Based on https://lincolnloop.com/blog/2008/mar/25/serving-django-cherrypy/
- Idea and code snippets borrowed from
  http://www.xhtml.net/scripts/Django-CherryPy-server-DjangoCerise
- Adapted to run as a management command.
- Some bugs fixed by RNC.
- Then rewritten by RNC.
- Then modified to serve CRATE, with static files, etc.
- Then daemonizing code removed: https://code.djangoproject.com/ticket/4996

TEST COMMAND:

.. code-block:: bash

    ./manage.py runcpserver --port 8080 --ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem --ssl_private_key /etc/ssl/private/ssl-cert-snakeoil.key

"""  # noqa: E501

from argparse import ArgumentParser, Namespace
import logging
import os
from typing import Any

import cherrypy
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from crate_anon.common.constants import EnvVar
from crate_anon.crateweb.config.wsgi import application as wsgi_application

# COULD ALSO USE:
#   from django.core.handlers.wsgi import WSGIHandler
#   wsgi_application = WSGIHandler()

log = logging.getLogger(__name__)


CRATE_STATIC_URL_PATH = settings.STATIC_URL.rstrip("/")
NEED_UNIX = "Need UNIX for group/user operations"

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    DEFAULT_ROOT = "/crate/root/path/"
else:
    DEFAULT_ROOT = settings.FORCE_SCRIPT_NAME


class Command(BaseCommand):
    """
    Django management command to run this project in a CherryPy web server.
    """

    help = (
        "Run this project in a CherryPy webserver. To do this, "
        "CherryPy is required (pip install cherrypy)."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        # docstring in superclass
        parser.add_argument(
            "--host",
            type=str,
            default="127.0.0.1",
            help="hostname to listen on (default: 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8088,
            help="port to listen on (default: 8088)",
        )
        parser.add_argument(
            "--server_name",
            type=str,
            default="localhost",
            help="CherryPy's SERVER_NAME environ entry (default: localhost)",
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=10,
            help="Number of threads for server to use (default: 10)",
        )
        parser.add_argument(
            "--ssl_certificate",
            type=str,
            help="SSL certificate file "
            "(e.g. /etc/ssl/certs/ssl-cert-snakeoil.pem)",
        )
        parser.add_argument(
            "--ssl_private_key",
            type=str,
            help="SSL private key file "
            "(e.g. /etc/ssl/private/ssl-cert-snakeoil.key)",
        )
        parser.add_argument(
            "--log_screen",
            dest="log_screen",
            action="store_true",
            help="log access requests etc. to terminal (default)",
        )
        parser.add_argument(
            "--no_log_screen",
            dest="log_screen",
            action="store_false",
            help="don't log access requests etc. to terminal",
        )
        parser.add_argument(
            "--debug_static",
            action="store_true",
            help="show debug info for static file requests",
        )
        parser.add_argument(
            "--root_path",
            type=str,
            default=DEFAULT_ROOT,
            help=f"Root path to serve CRATE at. Default: {DEFAULT_ROOT}",
        )
        parser.set_defaults(log_screen=True)
        # parser.add_argument(
        #     "--stop", action="store_true",
        #     help="stop server")

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        opts = Namespace(**options)
        # Activate the current language, because it won't get activated later.
        try:
            translation.activate(settings.LANGUAGE_CODE)
        except AttributeError:
            pass
        # noinspection PyTypeChecker
        runcpserver(opts)


class Missing:
    """
    CherryPy "application" that is a basic web interface to say "not here".
    """

    config = {
        "/": {
            # Anything so as to prevent complaints about an empty config.
            "tools.sessions.on": False,
        }
    }

    @cherrypy.expose
    def index(self) -> str:
        return (
            "[CRATE CherryPy server says:] "
            "Nothing to see here. Wrong URL path. "
            "(If you are sure it's right, has the server administrator "
            "set the 'root_path' option correctly?)"
        )


# noinspection PyUnresolvedReferences
def start_server(
    host: str,
    port: int,
    threads: int,
    server_name: str,
    root_path: str,
    log_screen: bool,
    ssl_certificate: str,
    ssl_private_key: str,
    debug_static: bool,
) -> None:
    """
    Start CherryPy server.

    Args:
        host: hostname to listen on (e.g. ``127.0.0.1``)
        port: port number to listen on
        threads: number of threads to use in the thread pool
        server_name: CherryPy SERVER_NAME environment variable (e.g.
            ``localhost``)
        root_path: root path to mount server at
        log_screen: show log to console?
        ssl_certificate: optional filename of an SSL certificate
        ssl_private_key: optional filename of an SSL private key
        debug_static: show debug info for static requests?
    """

    cherrypy.config.update(
        {
            "server.socket_host": host,
            "server.socket_port": port,
            "server.thread_pool": threads,
            "server.server_name": server_name,
            "server.log_screen": log_screen,
        }
    )
    if ssl_certificate and ssl_private_key:
        cherrypy.config.update(
            {
                "server.ssl_module": "builtin",
                "server.ssl_certificate": ssl_certificate,
                "server.ssl_private_key": ssl_private_key,
            }
        )

    log.info(f"Starting on host: {host}")
    log.info(f"Starting on port: {port}")
    log.info(
        f"Static files will be served from filesystem path: "
        f"{settings.STATIC_ROOT}"
    )
    log.info(
        f"Static files will be served at URL path: " f"{CRATE_STATIC_URL_PATH}"
    )
    log.info(f"CRATE will be at: {root_path}")
    log.info(f"Thread pool size: {threads}")

    static_config = {
        "/": {
            "tools.staticdir.root": settings.STATIC_ROOT,
            "tools.staticdir.debug": debug_static,
        },
        CRATE_STATIC_URL_PATH: {
            "tools.staticdir.on": True,
            "tools.staticdir.dir": "",
        },
    }
    cherrypy.tree.mount(Missing(), "", config=static_config)
    cherrypy.tree.graft(wsgi_application, root_path)

    # noinspection PyBroadException,PyPep8
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    except Exception:
        # 2017-03-13: shouldn't restrict to KeyboardInterrupt!
        cherrypy.engine.stop()


def runcpserver(opts: Namespace) -> None:
    """
    Launch the CherryPy server using arguments from an
    :class:`argparse.Namespace`.

    Args:
        opts: the command-line :class:`argparse.Namespace`
    """

    # Start the webserver
    log.info(f"starting server with options {opts}")
    start_server(
        host=opts.host,
        port=opts.port,
        threads=opts.threads,
        server_name=opts.server_name,
        root_path=opts.root_path,
        log_screen=opts.log_screen,
        ssl_certificate=opts.ssl_certificate,
        ssl_private_key=opts.ssl_private_key,
        debug_static=opts.debug_static,
    )


def main() -> None:
    """
    Command-line entry point (not typically used directly).
    """
    command = Command()
    parser = ArgumentParser()
    command.add_arguments(parser)
    cmdargs = parser.parse_args()
    runcpserver(cmdargs)


if __name__ == "__main__":
    main()
